from backend.app.core.ai.base import AIProvider


class ProviderRegistry:

    def __init__(self):
        self._providers: dict[str, AIProvider] = {}

    def register(
        self,
        name: str,
        provider: AIProvider,
    ):
        self._providers[name] = provider

    def get(
        self,
        name: str,
    ) -> AIProvider | None:
        return self._providers.get(name)

    def exists(
        self,
        name: str,
    ) -> bool:
        return name in self._providers

    def list(
        self,
    ) -> list[str]:
        return sorted(
            self._providers.keys()
        )


provider_registry = ProviderRegistry()
