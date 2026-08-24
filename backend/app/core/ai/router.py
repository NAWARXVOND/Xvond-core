from backend.app.core.ai.engine import ai_engine

from backend.app.modules.providers.models import (
    AIProviderRecord,
    CompanyAIProfile,
)


class AIProviderRouter:

    def resolve(
        self,
        db,
        company_id: int,
        requested_provider: str | None,
        requested_model: str | None,
    ) -> tuple[str, str]:

        if requested_provider and requested_model:
            if requested_provider in ai_engine.list_providers():
                return (
                    requested_provider,
                    requested_model,
                )

        profile = (
            db.query(CompanyAIProfile)
            .filter(
                CompanyAIProfile.company_id
                == company_id
            )
            .first()
        )

        if (
            profile
            and profile.default_provider
            and profile.default_model
            and profile.default_provider
            in ai_engine.list_providers()
        ):
            return (
                profile.default_provider,
                profile.default_model,
            )

        providers = (
            db.query(AIProviderRecord)
            .filter(
                AIProviderRecord.enabled.is_(True)
            )
            .order_by(
                AIProviderRecord.priority.asc()
            )
            .all()
        )

        for provider in providers:
            if provider.name in ai_engine.list_providers():
                return (
                    provider.name,
                    requested_model or "default",
                )

        if "mock" in ai_engine.list_providers():
            return (
                "mock",
                requested_model or "test-model",
            )

        raise ValueError(
            "No AI provider is available"
        )


ai_provider_router = AIProviderRouter()
