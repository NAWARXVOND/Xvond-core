from types import SimpleNamespace

from backend.app.core.ai.provider_policy import _candidate_score
from backend.app.modules.knowledge.embeddings import KnowledgeEmbeddingClient


def test_trivial_chat_skips_remote_semantic_lookup():
    client = KnowledgeEmbeddingClient()
    assert client._should_embed_query("مرحبا") is False
    assert client._should_embed_query("السلام عليكم") is False
    assert client._should_embed_query("thanks") is False
    assert client._should_embed_query("شو خدماتكم؟") is True
    assert client._should_embed_query("كم سعر الخدمة؟") is True
    client._client.close()


def test_automatic_route_prefers_proven_lower_latency_before_price():
    fast_model = SimpleNamespace(
        provider_name="openai",
        model_name="fast",
        input_price_per_million=10,
        output_price_per_million=10,
        id=1,
    )
    slow_model = SimpleNamespace(
        provider_name="openai",
        model_name="slow",
        input_price_per_million=1,
        output_price_per_million=1,
        id=2,
    )
    provider = SimpleNamespace(name="openai", priority=10)
    stats = {
        ("openai", "fast"): {"total": 10, "failed": 0, "latency_sum": 5000},
        ("openai", "slow"): {"total": 10, "failed": 0, "latency_sum": 20000},
    }
    assert _candidate_score(fast_model, provider, stats) < _candidate_score(
        slow_model,
        provider,
        stats,
    )


def test_automatic_route_prefers_observed_route_over_unmeasured_route():
    observed = SimpleNamespace(
        provider_name="openai",
        model_name="observed",
        input_price_per_million=5,
        output_price_per_million=5,
        id=1,
    )
    unknown = SimpleNamespace(
        provider_name="openai",
        model_name="unknown",
        input_price_per_million=1,
        output_price_per_million=1,
        id=2,
    )
    provider = SimpleNamespace(name="openai", priority=10)
    stats = {
        ("openai", "observed"): {"total": 5, "failed": 0, "latency_sum": 4000},
    }
    assert _candidate_score(observed, provider, stats) < _candidate_score(
        unknown,
        provider,
        stats,
    )
