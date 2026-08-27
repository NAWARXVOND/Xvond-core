import logging
import math
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
    """

    BATCH_SIZE = 64

    def __init__(self) -> None:
        self.provider = settings.KNOWLEDGE_EMBEDDING_PROVIDER
        self.model = settings.KNOWLEDGE_EMBEDDING_MODEL

    @property
    def available(self) -> bool:
        return bool(
            settings.KNOWLEDGE_SEMANTIC_ENABLED
            and self.provider == "openai"
            and settings.OPENAI_API_KEY
        )

    def _prepare_text(self, text: str) -> str:
        value = str(text or "").strip()
        if settings.AI_PII_REDACTION_ENABLED:
            value = protect_text(value).text
        return value

    def _embed_batch(self, values: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": values, "encoding_format": "float"}
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
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
        if not values or not self.available:
            return []
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(values), self.BATCH_SIZE):
                vectors.extend(self._embed_batch(values[start : start + self.BATCH_SIZE]))
            return vectors
        except Exception as exc:
            logger.warning("Knowledge embedding request failed; using lexical fallback: %s", exc)
            return []

    def embed_one(self, text: str) -> list[float] | None:
        vectors = self.embed_many([text])
        return vectors[0] if vectors else None

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
