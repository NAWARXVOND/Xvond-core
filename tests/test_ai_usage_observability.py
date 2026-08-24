from decimal import Decimal

from backend.app.modules.ai_agent.models import AIUsage


def test_ai_usage_observability_defaults():
    usage = AIUsage(
        company_id=1,
        agent_id=1,
        provider="groq",
        model="openai/gpt-oss-20b",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        provider_cost=Decimal("0"),
    )

    assert usage.status is None or usage.status == "success"
    assert usage.error_message is None
    assert usage.latency_ms is None or usage.latency_ms == 0


def test_failed_ai_usage_accepts_safe_error_metadata():
    usage = AIUsage(
        company_id=1,
        agent_id=1,
        provider="groq",
        model="openai/gpt-oss-20b",
        status="failed",
        error_message="provider timeout",
        latency_ms=1200,
    )

    assert usage.status == "failed"
    assert usage.error_message == "provider timeout"
    assert usage.latency_ms == 1200
