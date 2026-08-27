from backend.app.core.ai.routing_quality import required_quality_tier


def test_completed_transaction_does_not_force_future_simple_messages_up():
    message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: بدي احجز موعد\n"
        "assistant: تم تأكيد الحجز بنجاح.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمرحبا"
    )
    assert required_quality_tier(message) == 1
