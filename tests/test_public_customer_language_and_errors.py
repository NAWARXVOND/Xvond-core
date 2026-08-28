from fastapi import HTTPException

from backend.app.api.public_channels import (
    _dominant_message_language,
    _is_service_access_error,
    _safe_unavailable_message,
)


def test_english_message_is_detected_for_auto_reply_language():
    assert _dominant_message_language("Hello, I need help with my booking") == "en"


def test_arabic_message_is_detected_for_auto_reply_language():
    assert _dominant_message_language("مرحبا بدي احجز موعد") == "ar"


def test_service_limit_error_is_internal_and_recognized():
    exc = HTTPException(
        status_code=403,
        detail={
            "message": "Monthly service limit reached",
            "service": "ai_agents",
            "metric": "tokens",
            "used": "100",
            "limit": "90",
        },
    )
    assert _is_service_access_error(exc) is True
    public_text = _safe_unavailable_message("Hello")
    assert "limit" not in public_text.lower()
    assert "subscription" not in public_text.lower()
    assert "temporarily unavailable" in public_text.lower()


def test_safe_fallback_matches_customer_language():
    assert _safe_unavailable_message("Hello, can you help?").startswith("Sorry")
    assert _safe_unavailable_message("مرحبا ممكن تساعدني؟").startswith("عذرًا")
