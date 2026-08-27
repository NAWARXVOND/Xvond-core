from backend.app.core.ai.routing_quality import required_quality_tier


def test_short_booking_followup_keeps_action_quality():
    runtime_message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: بدي احجز موعد بكرا\n"
        "assistant: أكيد، شو الاسم ورقم الهاتف؟\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمحمد 99112233"
    )
    assert required_quality_tier(runtime_message) >= 2


def test_unrelated_question_after_completed_booking_can_drop_to_simple():
    runtime_message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: بدي احجز موعد بكرا\n"
        "assistant: تم تأكيد الحجز بنجاح.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمرحبا"
    )
    assert required_quality_tier(runtime_message) == 1


def test_simple_current_message_is_not_promoted_by_system_policy_words():
    runtime_message = (
        "Never claim a booking or order succeeded.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمرحبا"
    )
    assert required_quality_tier(runtime_message) == 1
