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


# Commercially useful quality bands. Packages can later cap the maximum tier
# without changing the routing algorithm itself.
MODEL_QUALITY_TIERS = {
    ("groq", "openai/gpt-oss-20b"): 1,
    ("groq", "openai/gpt-oss-120b"): 2,
    ("openai", "gpt-5-mini"): 2,
    ("openai", "gpt-5.6-luna"): 2,
    ("openai", "gpt-5.6-terra"): 3,
    ("openai", "gpt-5.6-sol"): 4,
    ("openai", "gpt-5.6"): 4,
}

_ACTION_TERMS = (
    "book", "booking", "reserve", "reservation", "appointment", "order",
    "cancel", "reschedule", "refund", "payment", "quote", "quotation",
    "حجز", "احجز", "موعد", "طلب", "اطلب", "إلغاء", "الغاء", "تعديل الموعد",
    "استرجاع", "دفع", "عرض سعر",
)

_ADVANCED_TERMS = (
    "compare", "analyse", "analyze", "recommend based on", "multiple conditions",
    "exception", "complaint", "escalation", "policy conflict", "complex",
    "قارن", "حلل", "حلّل", "شروط", "عدة خيارات", "استثناء", "شكوى",
    "تصعيد", "سياسة", "معقد", "معقّد",
)

_PREMIUM_TERMS = (
    "deep analysis", "detailed strategy", "multi-step reasoning", "root cause",
    "تحليل عميق", "استراتيجية مفصلة", "استراتيجية تفصيلية", "تحليل جذري",
)


def model_quality_tier(provider: str, model: str) -> int:
    """Return a stable quality band for routing and future package entitlements."""
    key = ((provider or "").strip().lower(), (model or "").strip().lower())
    if key in MODEL_QUALITY_TIERS:
        return MODEL_QUALITY_TIERS[key]
    model_name = key[1]
    if any(tag in model_name for tag in ("sol", "opus", "pro")):
        return 4
    if any(tag in model_name for tag in ("terra", "120b")):
        return 3
    if any(tag in model_name for tag in ("luna", "mini")):
        return 2
    return 2


def required_quality_tier(message: str | None) -> int:
    """Classify customer work without spending another model call just to route it.

    The classifier is intentionally conservative and deterministic: ordinary support
    stays cheap, operational actions get a stronger floor, and genuinely complex
    multi-condition requests are promoted. This avoids paying twice for every turn.
    """
    text = " ".join(str(message or "").lower().split())
    if not text:
        return 1

    premium_hits = sum(term in text for term in _PREMIUM_TERMS)
    advanced_hits = sum(term in text for term in _ADVANCED_TERMS)
    action_hits = sum(term in text for term in _ACTION_TERMS)
    separators = text.count(",") + text.count(";") + text.count("،") + text.count(" and ") + text.count(" و")

    if premium_hits or len(text) >= 1800 or (advanced_hits >= 2 and separators >= 3):
        return 4
    if advanced_hits or len(text) >= 700 or (action_hits and separators >= 4):
        return 3
    if action_hits or len(text) >= 280:
        return 2
    return 1


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
    eligible = [
        row for row in rows
        if model_quality_tier(row[0].provider_name, row[0].model_name) >= required_tier
    ]
    if not eligible and rows:
        strongest = max(model_quality_tier(row[0].provider_name, row[0].model_name) for row in rows)
        eligible = [
            row for row in rows
            if model_quality_tier(row[0].provider_name, row[0].model_name) == strongest
        ]
    eligible.sort(key=lambda row: _candidate_score(row[0], row[1], stats))
    return [
        ProviderSelection(
            provider=model.provider_name,
            model=model.model_name,
            reason=f"automatic:tier{required_tier}",
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

    Company-pinned models remain authoritative. In automatic mode Xvond first
    determines the minimum quality tier needed for the customer message, then picks
    the cheapest reliable enabled model that satisfies that floor. Remaining eligible
    models form the failover chain, so rate limits and provider failures do not become
    a single point of failure.
    """
    selections: list[ProviderSelection] = []
    profile = db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id == company_id).first()

    if profile and profile.default_provider and profile.default_model:
        _append_if_available(db, selections, profile.default_provider, profile.default_model, "company_default")
        if profile.allow_fallback:
            _append_if_available(db, selections, profile.fallback_provider, profile.fallback_model, "company_fallback")
            for candidate in _automatic_candidates(db, company_id, required_quality_tier(message)):
                if all((item.provider, item.model) != (candidate.provider, candidate.model) for item in selections):
                    selections.append(candidate)
    else:
        required_tier = required_quality_tier(message)
        for candidate in _automatic_candidates(db, company_id, required_tier):
            if all((item.provider, item.model) != (candidate.provider, candidate.model) for item in selections):
                selections.append(candidate)
        _append_if_available(db, selections, provider, model, "agent_preference")

    if not selections:
        raise ValueError("No enabled AI provider/model is available")
    return selections
