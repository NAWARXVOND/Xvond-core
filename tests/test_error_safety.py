import pytest

from backend.app.core.ai.base import AIProvider
from backend.app.core.ai.engine import ProviderExecutionError, ai_engine
from backend.app.core.ai.provider_registry import provider_registry
from backend.app.core.error_safety import safe_error_label, safe_error_metadata


class _LeakyProvider(AIProvider):
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        tools=None,
        tool_outputs=None,
        continuation=None,
    ):
        raise RuntimeError(
            "api-key-SECRET-123 customer said private-message body={sensitive}"
        )


def test_safe_error_helpers_never_persist_exception_text():
    error = RuntimeError("token=SUPER-SECRET customer payload")

    metadata = safe_error_metadata(error)
    label = safe_error_label(error)

    assert metadata == {
        "error_type": "RuntimeError",
        "error_category": "upstream",
        "retryable": False,
    }
    assert label == "upstream:RuntimeError"
    assert "SUPER-SECRET" not in str(metadata)
    assert "customer payload" not in str(metadata)
    assert "SUPER-SECRET" not in label


def test_ai_engine_contains_raw_provider_exception(monkeypatch):
    monkeypatch.setitem(provider_registry._providers, "mock", _LeakyProvider())

    with pytest.raises(ProviderExecutionError) as caught:
        ai_engine.generate(
            provider_name="mock",
            system_prompt="system",
            user_message="hello",
            model="test-model",
        )

    error = caught.value
    assert error.provider == "mock"
    assert error.error_type == "RuntimeError"
    assert str(error) == "mock provider failed (RuntimeError)"
    assert "SECRET-123" not in str(error)
    assert "private-message" not in str(error)
    assert "sensitive" not in str(error)
