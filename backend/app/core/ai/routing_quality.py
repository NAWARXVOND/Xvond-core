from contextvars import ContextVar


MODEL_QUALITY_TIERS = {
    ("groq", "openai/gpt-oss-20b"): 1,
    ("groq", "openai/gpt-oss-120b"): 2,
    ("openai", "gpt-5-mini"): 2,
    ("openai", "gpt-5.6-luna"): 2,
    ("openai", "gpt-5.6-terra"): 3,
    ("openai", "gpt-5.6-sol"): 4,
    ("openai", "gpt-5.6"): 4,
}

QUALITY_TIER_NAMES = {
    1: "simple",
    2: "standard",
    3: "advanced",
    4: "premium",
}

_MAX_QUALITY_TIER: ContextVar[int | None] = ContextVar(
    "xvond_max_quality_tier",
    default=None,
)

_ACTION_TERMS = (
    "book", "booking", "reserve", "reservation", "appointment", "order",
    "cancel", "reschedule", "refund", "payment", "quote", "quotation",
    "حجز", "احجز", "موعد", "طلب", "اطلب", "إلغاء", "الغاء", "تعديل الموعد",
    "استرجاع", "دفع", "عرض سعر",
)

_ACTION_DETAIL_TERMS = (
    "name", "phone", "mobile", "number", "date", "time", "service", "branch",
    "address", "quantity", "اسم", "رقم", "هاتف", "جوال", "تاريخ", "موعد",
    "ساعة", "وقت", "خدمة", "فرع", "عنوان", "كمية",
)

_ACTION_COMPLETION_TERMS = (
    "booking confirmed", "reservation confirmed", "order confirmed", "successfully booked",
    "successfully placed", "completed successfully", "تم تأكيد الحجز", "تم الحجز",
    "تم تأكيد الطلب", "تم الطلب", "تم تنفيذ", "بنجاح",
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

_CUSTOMER_MESSAGE_MARKER = "CURRENT CUSTOMER MESSAGE (answer this intent directly):"
_HISTORY_MARKER = "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):"


def normalize_quality_tier(value) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        tier = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_quality_tier must be an integer from 1 to 4") from exc
    if tier not in QUALITY_TIER_NAMES:
        raise ValueError("max_quality_tier must be between 1 and 4")
    return tier


def set_quality_tier_cap(value) -> int | None:
    """Set the per-request commercial model-quality ceiling."""
    tier = normalize_quality_tier(value)
    _MAX_QUALITY_TIER.set(tier)
    return tier


def current_quality_tier_cap() -> int | None:
    return _MAX_QUALITY_TIER.get()


def model_quality_tier(provider: str, model: str) -> int:
    """Return the routing/commercial quality band for a provider model."""
    key = ((provider or "").strip().lower(), (model or "").strip().lower())
    if key in MODEL_QUALITY_TIERS:
        return MODEL_QUALITY_TIERS[key]
    model_name = key[1]
    if any(tag in model_name for tag in ("sol", "opus", "pro")):
        return 4
    if any(tag in model_name for tag in ("terra",)):
        return 3
    if any(tag in model_name for tag in ("120b", "luna", "mini")):
        return 2
    return 2


def model_allowed_by_quality_cap(provider: str, model: str) -> bool:
    cap = current_quality_tier_cap()
    return cap is None or model_quality_tier(provider, model) <= cap


def _normalized(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _split_runtime_message(message: str | None) -> tuple[str, str]:
    raw = str(message or "")
    if _CUSTOMER_MESSAGE_MARKER not in raw:
        return "", _normalized(raw)

    before, current = raw.rsplit(_CUSTOMER_MESSAGE_MARKER, 1)
    history = ""
    if _HISTORY_MARKER in before:
        history = before.rsplit(_HISTORY_MARKER, 1)[-1]
    return _normalized(history[-1600:]), _normalized(current)


def _active_action_continuation(history: str, current: str) -> bool:
    if not history or not current or len(current) > 120:
        return False
    recent_history = history[-500:]
    if any(term in recent_history for term in _ACTION_COMPLETION_TERMS):
        return False
    has_action = any(term in recent_history for term in _ACTION_TERMS)
    has_detail_prompt = any(term in recent_history for term in _ACTION_DETAIL_TERMS)
    return has_action and has_detail_prompt


def required_quality_tier(message: str | None) -> int:
    """Estimate the minimum useful model tier without paying for a classifier call."""
    history, text = _split_runtime_message(message)
    if not text:
        return 1

    premium_hits = sum(term in text for term in _PREMIUM_TERMS)
    advanced_hits = sum(term in text for term in _ADVANCED_TERMS)
    action_hits = sum(term in text for term in _ACTION_TERMS)
    separators = (
        text.count(",")
        + text.count(";")
        + text.count("،")
        + text.count(" and ")
        + text.count(" و")
    )

    if premium_hits or len(text) >= 1800 or (advanced_hits >= 2 and separators >= 3):
        return 4
    if advanced_hits or len(text) >= 700 or (action_hits and separators >= 4):
        return 3
    if action_hits or len(text) >= 280 or _active_action_continuation(history, text):
        return 2
    return 1


def effective_required_quality_tier(message: str | None) -> int:
    required = required_quality_tier(message)
    cap = current_quality_tier_cap()
    return min(required, cap) if cap is not None else required


def assert_model_quality(provider: str, model: str, message: str | None) -> None:
    required = effective_required_quality_tier(message)
    actual = model_quality_tier(provider, model)
    cap = current_quality_tier_cap()
    if cap is not None and actual > cap:
        raise ValueError(
            f"Model quality tier {actual} exceeds package tier cap {cap}; trying allowed fallback"
        )
    if actual < required:
        raise ValueError(
            f"Model quality tier {actual} is below required tier {required}; trying stronger fallback"
        )
