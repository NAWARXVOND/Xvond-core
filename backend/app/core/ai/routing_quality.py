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

_CUSTOMER_MESSAGE_MARKER = "CURRENT CUSTOMER MESSAGE (answer this intent directly):"


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


def _customer_text(message: str | None) -> str:
    text = str(message or "")
    if _CUSTOMER_MESSAGE_MARKER in text:
        text = text.rsplit(_CUSTOMER_MESSAGE_MARKER, 1)[-1]
    return " ".join(text.lower().split())


def required_quality_tier(message: str | None) -> int:
    """Estimate the minimum useful model tier without paying for a classifier call."""
    text = _customer_text(message)
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
    if action_hits or len(text) >= 280:
        return 2
    return 1


def assert_model_quality(provider: str, model: str, message: str | None) -> None:
    required = required_quality_tier(message)
    actual = model_quality_tier(provider, model)
    if actual < required:
        raise ValueError(
            f"Model quality tier {actual} is below required tier {required}; trying stronger fallback"
        )
