from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_embedding_client_reuses_persistent_http_connection():
    code = source("backend/app/modules/knowledge/embeddings.py")
    assert "self._client = httpx.Client(" in code
    assert "response = self._client.post(" in code
    assert "with httpx.Client(" not in code


def test_embedding_lookup_is_latency_bounded_and_cached():
    code = source("backend/app/modules/knowledge/embeddings.py")
    assert "read=8.0" in code
    assert "connect=3.0" in code
    assert "QUERY_CACHE_TTL_SECONDS = 300.0" in code
    assert "QUERY_CACHE_MAX_ITEMS = 256" in code
    assert "cached = self._cache_get(value)" in code
    assert "self._cache_put(value, vector)" in code


def test_embedding_failure_keeps_lexical_fallback_available():
    code = source("backend/app/modules/knowledge/embeddings.py")
    assert "FAILURE_COOLDOWN_SECONDS = 60.0" in code
    assert "using lexical fallback" in code
    assert "return None" in code
