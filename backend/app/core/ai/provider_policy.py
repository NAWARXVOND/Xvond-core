from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import inspect

from backend.app.core.ai.engine import ai_engine
from backend.app.core.ai.routing_quality import (
    current_quality_tier_cap,
    effective_required_quality_tier,
    model_allowed_by_quality_cap,
    model_quality_tier,
)
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
    if not model_allowed_by_quality_cap(provider, model):
        raise ValueError("AI provider/model exceeds the active package quality tier")
    return ProviderSelection(provider=provider.strip(), model=model.strip(), reason="requested")


def _append_if_available(
    db,
    selections: list[ProviderSelection],
    provider: str | None,
    model: str | None,
    reason: str,
):
    provider = (provider or "").strip()
    model = (model or "").strip()
    if not provider or not model or not provider_model_available(db, provider, model):
        return
    if not model_allowed_by_quality_cap(provider, model):
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
        price,
        round(average_latency, 2),
        int(provider.priority or 100),
        int(model.id or 0),
    )


def _automatic_candidates(db, company_id: int, required_tier: int = 1) -> list[ProviderSelection]:
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

    cap = current_quality_tier_cap()
    if cap is not None:
        required_tier = min(required_tier, cap)

    def allowed(row) -> bool:
        tier = model_quality_tier(row[0].provider_name, row[0].model_name)
        return tier >= required_tier and (cap is None or tier <= cap)

    eligible = [row for row in rows if allowed(row)]
    if not eligible and rows:
        allowed_rows = [
            row for row in rows
            if cap is None
            or model_quality_tier(row[0].provider_name, row[0].model_name) <= cap
        ]
        if allowed_rows:
            strongest = max(
                model_quality_tier(row[0].provider_name, row[0].model_name)
                for row in allowed_rows
            )
            eligible = [
                row for row in allowed_rows
                if model_quality_tier(row[0].provider_name, row[0].model_name) == strongest
            ]

    eligible.sort(key=lambda row: _candidate_score(row[0], row[1], stats))
    reason_suffix = f":cap{cap}" if cap is not None else ""
    return [
        ProviderSelection(
            provider=model.provider_name,
            model=model.model_name,
            reason=f"automatic:tier{required_tier}{reason_suffix}",
        )
        for model, _provider in eligible
    ]


def runtime_selections(
    db,
    company_id: int,
    provider: str | None,
    model: str | None,
    message: str | None = None,
) -> list[ProviderSelection]:
    """Build the provider/model route for one request.

    Company-pinned models remain first when they fit the active package ceiling.
    In automatic mode Xvond ranks eligible models by reliability, cost, latency
    and admin priority. The package max_quality_tier is a hard ceiling while the
    runtime quality classifier chooses the cheapest sufficient model inside it.
    """
    selections: list[ProviderSelection] = []
    profile = db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id == company_id).first()
    required_tier = effective_required_quality_tier(message)

    if profile and profile.default_provider and profile.default_model:
        _append_if_available(
            db,
            selections,
            profile.default_provider,
            profile.default_model,
            "company_default",
        )
        if profile.allow_fallback:
            _append_if_available(
                db,
                selections,
                profile.fallback_provider,
                profile.fallback_model,
                "company_fallback",
            )
            for candidate in _automatic_candidates(db, company_id, required_tier):
                if all(
                    (item.provider, item.model) != (candidate.provider, candidate.model)
                    for item in selections
                ):
                    selections.append(candidate)
    else:
        for candidate in _automatic_candidates(db, company_id, required_tier):
            if all(
                (item.provider, item.model) != (candidate.provider, candidate.model)
                for item in selections
            ):
                selections.append(candidate)
        _append_if_available(db, selections, provider, model, "agent_preference")

    if not selections:
        cap = current_quality_tier_cap()
        if cap is not None:
            raise ValueError(
                f"No enabled AI provider/model is available within package quality tier {cap}"
            )
        raise ValueError("No enabled AI provider/model is available")
    return selections
