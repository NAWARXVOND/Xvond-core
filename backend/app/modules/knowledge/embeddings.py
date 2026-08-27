import logging
import math
from typing import Iterable

import httpx

from backend.app.core.config.settings import settings

logger = logging.getLogger(__name__)


class KnowledgeEmbeddingClient:
    """Small provider boundary for semantic knowledge embeddings.

    Semantic retrieval is enabled only when explicitly configured and a supported
    provider credential is available. Failures never take the agent offline; the
    knowledge service falls back to lexical retrieval.
    """

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

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        values = [str(text or "").strip() for text in texts]
        if not values:
            return []
        if not self.available:
            return []
        payload = {"model": self.model, "input": values, "encoding_format": "float"}
        try:
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
            if len(vectors) != len(values) or any(not isinstance(v, list) for v in vectors):
                raise RuntimeError("Embedding provider returned an incomplete response")
            return [[float(number) for number in vector] for vector in vectors]
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
