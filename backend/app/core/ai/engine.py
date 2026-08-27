from backend.app.core.ai.base import (
    AIProvider,
    AIResponse,
)
from backend.app.core.ai.provider_registry import (
    provider_registry,
)
from backend.app.core.ai.routing_quality import assert_model_quality
from backend.app.core.config.settings import settings
from backend.app.core.privacy import (
    protect_text,
    protect_tool_outputs,
    restore_ai_response,
)


class AIEngine:

    def __init__(self):
        self._load_core_providers()

    def _load_core_providers(self):
        if not settings.is_production:
            from backend.app.core.ai.providers.mock import MockProvider
            provider_registry.register("mock", MockProvider())

        if settings.OPENAI_API_KEY:
            try:
                from backend.app.core.ai.providers.openai import OpenAIProvider
                provider_registry.register("openai", OpenAIProvider())
            except Exception as exc:
                print("Could not load OpenAI provider:", exc)

        if settings.GROQ_API_KEY:
            try:
                from backend.app.core.ai.providers.groq import GroqProvider
                provider_registry.register("groq", GroqProvider())
            except Exception as exc:
                print("Could not load Groq provider:", exc)

        if settings.ANTHROPIC_API_KEY:
            try:
                from backend.app.core.ai.providers.anthropic import AnthropicProvider
                provider_registry.register("anthropic", AnthropicProvider())
            except Exception as exc:
                print("Could not load Anthropic provider:", exc)

        if settings.GOOGLE_API_KEY:
            try:
                from backend.app.core.ai.providers.google import GoogleProvider
                provider_registry.register("google", GoogleProvider())
            except Exception as exc:
                print("Could not load Google provider:", exc)

        if settings.XAI_API_KEY:
            try:
                from backend.app.core.ai.providers.xai import XAIProvider
                provider_registry.register("xai", XAIProvider())
            except Exception as exc:
                print("Could not load xAI provider:", exc)

    def register_provider(self, name: str, provider: AIProvider):
        provider_registry.register(name, provider)

    def get_provider(self, provider_name: str) -> AIProvider:
        provider = provider_registry.get(provider_name)
        if provider is None:
            raise ValueError(f"AI provider '{provider_name}' is not configured")
        return provider

    def generate(
        self,
        provider_name: str,
        system_prompt: str,
        user_message: str,
        model: str,
        tools: list[dict] | None = None,
        tool_outputs: list | None = None,
        continuation=None,
    ) -> AIResponse:
        if provider_name != "mock":
            assert_model_quality(provider_name, model, user_message)

        provider = self.get_provider(provider_name)
        replacements: dict[str, str] | None = None
        outbound_system_prompt = system_prompt
        outbound_user_message = user_message
        outbound_tool_outputs = tool_outputs

        if settings.AI_PII_REDACTION_ENABLED and provider_name != "mock":
            replacements = {}
            outbound_system_prompt = protect_text(
                system_prompt,
                replacements,
            ).text
            outbound_user_message = protect_text(
                user_message,
                replacements,
            ).text
            outbound_tool_outputs = protect_tool_outputs(
                tool_outputs,
                replacements,
            )

        response = provider.generate(
            system_prompt=outbound_system_prompt,
            user_message=outbound_user_message,
            model=model,
            tools=tools,
            tool_outputs=outbound_tool_outputs,
            continuation=continuation,
        )

        if replacements:
            response = restore_ai_response(response, replacements)
        return response

    def list_providers(self) -> list[str]:
        return provider_registry.list()


ai_engine = AIEngine()
