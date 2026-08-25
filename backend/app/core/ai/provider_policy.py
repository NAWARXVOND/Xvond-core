from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import inspect

from backend.app.core.ai.engine import ai_engine
from backend.app.modules.ai_agent.models import AIUsage
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


def _recent_runtime_stats(db, company_id: int) -> dict[tuple[str, str], dict]:
    """Return recent per-model reliability and latency without requiring new schema."""
    try:
        if not inspect(db.get_bind()).has_table("ai_usage"):
            return {}
        cutoff = datetime.utcnow() - timedelta(hours=24)
        rows = db.query(AIUsage).filter(
            AIUsage.company_id == company_id,
            AIUsage.created_at >= cutoff,
        ).order_by(AIUsage.id.desc()).limit(300).all()
    except Exception:
        return {}

    stats: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.provider, row.model)
        item = stats.setdefault(key, {"total": 0, "failed": 0, "latency_sum": 0})
        item["total"] += 1
        if row.status != "success":
            item["failed"] += 1
        if row.latency_ms and row.latency_ms > 0:
            item["latency_sum"] += row.latency_ms
    return stats


def _candidate_score(model: AIModelRecord, provider: AIProviderRecord, stats: dict) -> tuple:
    runtime = stats.get((model.provider_name, model.model_name), {})
    total = int(runtime.get("total", 0) or 0)
    failed = int(runtime.get("failed", 0) or 0)
    failure_rate = (failed / total) if total else 0.0
    average_latency = (int(runtime.get("latency_sum", 0) or 0) / total) if total else 0.0
    price = Decimal(model.input_price_per_million or 0) + Decimal(model.output_price_per_million or 0)
    return (
        1 if provider.name == "mock" else 0,
        round(failure_rate, 4),
        int(provider.priority or 100),
        round(average_latency, 2),
        price,
        int(model.id or 0),
    )


def _automatic_candidates(db, company_id: int) -> list[ProviderSelection]:
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
    stats = _recent_runtime_stats(db, company_id)
    rows = [row for row in rows if row[1].name in loaded]
    rows.sort(key=lambda row: _candidate_score(row[0], row[1], stats))
    return [
        ProviderSelection(provider=model.provider_name, model=model.model_name, reason="automatic")
        for model, _provider in rows
    ]


def runtime_selections(
    db,
    company_id: int,
    provider: str | None,
    model: str | None,
) -> list[ProviderSelection]:
    """Build the full provider/model route for one company request.

    If the company explicitly pins a default model, that policy is respected first.
    Otherwise Xvond automatically ranks every loaded/enabled model using recent
    reliability, admin priority, latency and configured token price. Remaining
    providers form the failover chain so one vendor is never a single point of failure.
    """
    selections: list[ProviderSelection] = []
    profile = db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id == company_id).first()

    if profile and profile.default_provider and profile.default_model:
        _append_if_available(db, selections, profile.default_provider, profile.default_model, "company_default")
        if profile.allow_fallback:
            _append_if_available(db, selections, profile.fallback_provider, profile.fallback_model, "company_fallback")
            for candidate in _automatic_candidates(db, company_id):
                if all((item.provider, item.model) != (candidate.provider, candidate.model) for item in selections):
                    selections.append(candidate)
    else:
        for candidate in _automatic_candidates(db, company_id):
            if all((item.provider, item.model) != (candidate.provider, candidate.model) for item in selections):
                selections.append(candidate)
        # A legacy agent choice is only used if it was not already part of the automatic pool.
        _append_if_available(db, selections, provider, model, "agent_preference")

    if not selections:
        raise ValueError("No enabled AI provider/model is available")
    return selections
