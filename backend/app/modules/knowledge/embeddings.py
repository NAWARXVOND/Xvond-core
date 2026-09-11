import hashlib
import logging
import math
from collections import OrderedDict
from time import monotonic
from typing import Iterable

import httpx

from backend.app.core.config.settings import settings
from backend.app.core.privacy import protect_text

logger = logging.getLogger(__name__)


class KnowledgeEmbeddingClient:
    """Provider boundary for semantic knowledge embeddings.

    Semantic retrieval is enabled only when configured and a supported provider
    credential is available. Failures never take the AI employee offline; callers
    can safely fall back to deterministic lexical retrieval.

    This path runs synchronously before the main AI response, so it must stay
    latency-bounded. Reuse one HTTP client instead of creating a fresh TLS
    connection for every customer message, and keep a small short-lived cache for
    repeated queries.
    """

    BATCH_SIZE = 64
    FAILURE_COOLDOWN_SECONDS = 60.0
    QUERY_CACHE_TTL_SECONDS = 300.0
    QUERY_CACHE_MAX_ITEMS = 256

    def __init__(self) -> None:
        self.provider = settings.KNOWLEDGE_EMBEDDING_PROVIDER
        self.model = settings.KNOWLEDGE_EMBEDDING_MODEL
        self._retry_after = 0.0
        self._query_cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=3.0, read=8.0, write=8.0, pool=3.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
        )

    @property
    def available(self) -> bool:
        return bool(
            settings.KNOWLEDGE_SEMANTIC_ENABLED
            and self.provider == "openai"
            and settings.OPENAI_API_KEY
        )

    @property
    def ready(self) -> bool:
        return self.available and monotonic() >= self._retry_after

    def _prepare_text(self, text: str) -> str:
        value = str(text or "").strip()
        if settings.AI_PII_REDACTION_ENABLED:
            value = protect_text(value).text
        return value

    def _cache_key(self, value: str) -> str:
        payload = f"{self.provider}:{self.model}:{value}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _cache_get(self, value: str) -> list[float] | None:
        key = self._cache_key(value)
        cached = self._query_cache.get(key)
        if cached is None:
            return None
        expires_at, vector = cached
        if monotonic() >= expires_at:
            self._query_cache.pop(key, None)
            return None
        self._query_cache.move_to_end(key)
        return vector

    def _cache_put(self, value: str, vector: list[float]) -> None:
        key = self._cache_key(value)
        self._query_cache[key] = (
            monotonic() + self.QUERY_CACHE_TTL_SECONDS,
            vector,
        )
        self._query_cache.move_to_end(key)
        while len(self._query_cache) > self.QUERY_CACHE_MAX_ITEMS:
            self._query_cache.popitem(last=False)

    def _embed_batch(self, values: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": values, "encoding_format": "float"}
        response = self._client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors = [item.get("embedding") for item in ordered]
        if len(vectors) != len(values) or any(not isinstance(vector, list) for vector in vectors):
            raise RuntimeError("Embedding provider returned an incomplete response")
        return [[float(number) for number in vector] for vector in vectors]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        values = [self._prepare_text(text) for text in texts]
        if not values or not self.ready:
            return []
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(values), self.BATCH_SIZE):
                vectors.extend(self._embed_batch(values[start : start + self.BATCH_SIZE]))
            self._retry_after = 0.0
            return vectors
        except Exception as exc:
            self._retry_after = monotonic() + self.FAILURE_COOLDOWN_SECONDS
            logger.warning("Knowledge embedding request failed; using lexical fallback: %s", exc)
            return []

    def embed_one(self, text: str) -> list[float] | None:
        value = self._prepare_text(text)
        if not value or not self.ready:
            return None
        cached = self._cache_get(value)
        if cached is not None:
            return cached
        try:
            vectors = self._embed_batch([value])
            self._retry_after = 0.0
        except Exception as exc:
            self._retry_after = monotonic() + self.FAILURE_COOLDOWN_SECONDS
            logger.warning("Knowledge embedding request failed; using lexical fallback: %s", exc)
            return None
        if not vectors:
            return None
        vector = vectors[0]
        self._cache_put(value, vector)
        return vector

    @staticmethod
    def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float | None:
        if not left or not right or len(left) != len(right):
            return None
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return None
        return dot / (left_norm * right_norm)


knowledge_embedding_client = KnowledgeEmbeddingClient()
