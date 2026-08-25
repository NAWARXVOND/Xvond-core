from dataclasses import dataclass

from backend.app.core.ai.engine import ai_engine
from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
    CompanyAIProfile,
)


@dataclass(frozen=True)
class ProviderSelection:
    provider: str
    model: str


def provider_model_available(
    db,
    provider: str,
    model: str,
) -> bool:
    provider = (provider or "").strip()
    model = (model or "").strip()

    if (
        not provider
        or not model
        or provider not in ai_engine.list_providers()
    ):
        return False

    provider_record = (
        db.query(AIProviderRecord)
        .filter(
            AIProviderRecord.name == provider,
            AIProviderRecord.enabled.is_(True),
        )
        .first()
    )
    if provider_record is None:
        return False

    model_record = (
        db.query(AIModelRecord)
        .filter(
            AIModelRecord.provider_name == provider,
            AIModelRecord.model_name == model,
            AIModelRecord.enabled.is_(True),
        )
        .first()
    )
    return model_record is not None


def require_provider_model(
    db,
    provider: str,
    model: str,
) -> ProviderSelection:
    if not provider_model_available(
        db,
        provider,
        model,
    ):
        raise ValueError(
            "AI provider/model is not loaded and enabled"
        )

    return ProviderSelection(
        provider=provider.strip(),
        model=model.strip(),
    )


def runtime_selections(
    db,
    company_id: int,
    provider: str,
    model: str,
) -> list[ProviderSelection]:
    selections = [
        require_provider_model(
            db,
            provider,
            model,
        )
    ]

    profile = (
        db.query(CompanyAIProfile)
        .filter(
            CompanyAIProfile.company_id == company_id
        )
        .first()
    )

    if (
        profile is None
        or not profile.allow_fallback
        or not profile.fallback_provider
        or not profile.fallback_model
    ):
        return selections

    fallback = ProviderSelection(
        provider=profile.fallback_provider.strip(),
        model=profile.fallback_model.strip(),
    )

    if (
        fallback not in selections
        and provider_model_available(
            db,
            fallback.provider,
            fallback.model,
        )
    ):
        selections.append(fallback)

    return selections
