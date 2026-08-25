from backend.app.core.config.settings import settings
from backend.app.core.ai.providers.groq import GroqProvider


def test_groq_provider_uses_chat_completions_for_local_tool_loop(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    provider = GroqProvider()

    assert provider.api_key == "test-key"
    assert provider._request_url() == "https://api.groq.com/openai/v1/chat/completions"


def test_groq_converts_xvond_tools_to_chat_function_schema(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    provider = GroqProvider()
    tools = provider._convert_chat_tools([
        {
            "name": "booking",
            "description": "Create booking",
            "input_schema": {"type": "object", "properties": {"date": {"type": "string"}}},
        }
    ])
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "booking"
    assert tools[0]["function"]["parameters"]["properties"]["date"]["type"] == "string"
