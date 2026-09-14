import logging

from backend.app.core.ai.base import (
    AIProvider,
    AIResponse,
)
from backend.app.core.ai.provider_registry import (
    provider_registry,
)
from backend.app.core.ai.response_language import apply_response_language
from backend.app.core.ai.routing_quality import assert_model_quality
from backend.app.core.config.settings import settings
from backend.app.core.error_safety import safe_error_metadata, safe_error_type
from backend.app.core.privacy import (
    protect_text,
    protect_tool_outputs,
    restore_ai_response,
)


logger = logging.getLogger("xvond.ai.engine")


class ProviderExecutionError(RuntimeError):
    """Safe provider-boundary error.

    Raw SDK/provider exception text must never escape into runtime responses,
    AIUsage, audit details, or customer-visible routing metadata because upstream
    errors can contain prompts, request bodies, credentials, or customer data.
    """

    def __init__(self, provider: str, error: BaseException):
        self.provider = str(provider or "unknown")[:100]
        self.error_type = safe_error_type(error)
        super().__init__(f"{self.provider} provider failed ({self.error_type})")


class AIEngine:

    def __init__(self):
        self._load_core_providers()

    def _register_core_provider(self, name: str, factory) -> None:
        try:
            provider_registry.register(name, factory())
        except Exception as exc:
            logger.error(
                "AI provider could not be loaded",
                extra={"provider": name, **safe_error_metadata(exc)},
            )

    def _load_core_providers(self):
        if not settings.is_production:
            from backend.app.core.ai.providers.mock import MockProvider
            provider_registry.register("mock", MockProvider())

        if settings.OPENAI_API_KEY:
            from backend.app.core.ai.providers.openai import OpenAIProvider
            self._register_core_provider("openai", OpenAIProvider)

        if settings.ANTHROPIC_API_KEY:
            from backend.app.core.ai.providers.anthropic import AnthropicProvider
            self._register_core_provider("anthropic", AnthropicProvider)

        if settings.GOOGLE_API_KEY:
            from backend.app.core.ai.providers.google import GoogleProvider
            self._register_core_provider("google", GoogleProvider)

        if settings.XAI_API_KEY:
            from backend.app.core.ai.providers.xai import XAIProvider
            self._register_core_provider("xai", XAIProvider)

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
        # Language is an AI Employee policy, not a channel policy. Apply it here so
        # Website, WhatsApp, Voice, test chat and future channels all behave the same.
        runtime_system_prompt = apply_response_language(system_prompt, user_message)
        outbound_system_prompt = runtime_system_prompt
        outbound_user_message = user_message
        outbound_tool_outputs = tool_outputs

        if settings.AI_PII_REDACTION_ENABLED and provider_name != "mock":
            replacements = {}
            outbound_system_prompt = protect_text(
                runtime_system_prompt,
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

        try:
            response = provider.generate(
                system_prompt=outbound_system_prompt,
                user_message=outbound_user_message,
                model=model,
                tools=tools,
                tool_outputs=outbound_tool_outputs,
                continuation=continuation,
            )
        except ProviderExecutionError:
            raise
        except Exception as exc:
            logger.warning(
                "AI provider request failed",
                extra={"provider": provider_name, "model": model, **safe_error_metadata(exc)},
            )
            raise ProviderExecutionError(provider_name, exc) from exc

        if replacements:
            response = restore_ai_response(response, replacements)
        return response

    def list_providers(self) -> list[str]:
        return provider_registry.list()


ai_engine = AIEngine()
