from backend.app.core.config.settings import settings
from backend.app.core.ai.providers.groq import GroqProvider


def test_groq_provider_uses_official_responses_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    provider = GroqProvider()

    assert provider.api_key == "test-key"
    assert provider._request_url() == "https://api.groq.com/openai/v1/responses"
