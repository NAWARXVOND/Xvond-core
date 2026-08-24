
from backend.app.core.ai.providers.openai import (
    OpenAIProvider,
)
from backend.app.core.config.settings import settings


class XAIProvider(OpenAIProvider):

    def __init__(self):

        if not settings.XAI_API_KEY:
            raise ValueError(
                "XAI_API_KEY is not configured"
            )

        self.api_key = settings.XAI_API_KEY

    def _request_url(self) -> str:
        return "https://api.x.ai/v1/responses"
