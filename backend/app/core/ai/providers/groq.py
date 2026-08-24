from backend.app.core.ai.providers.openai import OpenAIProvider
from backend.app.core.config.settings import settings


class GroqProvider(OpenAIProvider):
    """Groq Responses API provider using its OpenAI-compatible endpoint."""

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured")

        self.api_key = settings.GROQ_API_KEY

    def _request_url(self) -> str:
        return "https://api.groq.com/openai/v1/responses"
