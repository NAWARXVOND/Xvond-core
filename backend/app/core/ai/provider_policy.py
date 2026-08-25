from dataclasses import dataclass
from decimal import Decimal

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
    reason: str = "automatic"


def provider_model_available(db, provider: str, model: str) -> bool:
    provider = (provider or "").strip()
    model = (model or "").strip()
    if not provider or not model or provider not in ai_engine.list_providers():
        return False
    provider_record = db.query(AIProviderRecord).filter(
        AIProviderRecord.name == provider,
        AIProviderRecord.enabled.is_(True),
    ).first()
    if provider_record is None:
        return False
    return db.query(AIModelRecord).filter(
        AIModelRecord.provider_name == provider,
        AIModelRecord.model_name == model,
        AIModelRecord.enabled.is_(True),
    ).first() is not None


def require_provider_model(db, provider: str, model: str) -> ProviderSelection:
    if not provider_model_available(db, provider, model):
        raise ValueError("AI provider/model is not loaded and enabled")
    return ProviderSelection(provider=provider.strip(), model=model.strip(), reason="requested")


def _append_if_available(db, selections: list[ProviderSelection], provider: str | None, model: str | None, reason: str):
    provider = (provider or "").strip()
    model = (model or "").strip()
    if not provider or not model or not provider_model_available(db, provider, model):
        return
    candidate = ProviderSelection(provider=provider, model=model, reason=reason)
    if all((item.provider, item.model) != (candidate.provider, candidate.model) for item in selections):
        selections.append(candidate)


def _automatic_candidates(db) -> list[ProviderSelection]:
    loaded = set(ai_engine.list_providers())
    rows = (
        db.query(AIModelRecord, AIProviderRecord)
        .join(AIProviderRecord, AIProviderRecord.name == AIModelRecord.provider_name)
        .filter(
            AIModelRecord.enabled.is_(True),
            AIProviderRecord.enabled.is_(True),
        )
        .all()
    )
    rows.sort(
        key=lambda row: (
            1 if row[1].name == "mock" else 0,
            int(row[1].priority or 100),
            Decimal(row[0].input_price_per_million or 0) + Decimal(row[0].output_price_per_million or 0),
            int(row[0].id or 0),
        )
    )
    return [
        ProviderSelection(provider=model.provider_name, model=model.model_name, reason="automatic")
        for model, provider in rows
        if provider.name in loaded
    ]


def runtime_selections(
    db,
    company_id: int,
    provider: str | None,
    model: str | None,
) -> list[ProviderSelection]:
    """Return a complete provider/model failover chain for runtime use.

    Existing agent/provider choices are preferences, not a single point of failure.
    Xvond then appends every loaded and enabled model so an outage or quota problem
    at one vendor can fall through to the next available provider automatically.
    """
    selections: list[ProviderSelection] = []
    profile = db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id == company_id).first()

    # Company policy wins when explicitly configured.
    if profile:
        _append_if_available(db, selections, profile.default_provider, profile.default_model, "company_default")

    # Keep the employee's current model as a preference for backward compatibility.
    _append_if_available(db, selections, provider, model, "agent_preference")

    # Preserve the explicit legacy fallback as the next preferred route.
    if profile and profile.allow_fallback:
        _append_if_available(db, selections, profile.fallback_provider, profile.fallback_model, "company_fallback")

    # Automatic multi-provider routing: append all remaining enabled/loaded models.
    if profile is None or profile.allow_fallback:
        for candidate in _automatic_candidates(db):
            if all((item.provider, item.model) != (candidate.provider, candidate.model) for item in selections):
                selections.append(candidate)

    if not selections:
        raise ValueError("No enabled AI provider/model is available")
    return selections
