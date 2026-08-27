from backend.app.core.ai.routing_quality import required_quality_tier


def test_short_booking_followup_keeps_action_quality():
    runtime_message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: بدي احجز موعد بكرا\n"
        "assistant: أكيد، شو الاسم ورقم الهاتف؟\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمحمد 99112233"
    )
    assert required_quality_tier(runtime_message) == 2


def test_english_booking_followup_keeps_action_quality():
    runtime_message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: I want to book an appointment\n"
        "assistant: What name and phone number should I use?\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nNawar"
    )
    assert required_quality_tier(runtime_message) == 2


def test_completed_booking_does_not_force_simple_message_up():
    runtime_message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: بدي احجز موعد بكرا\n"
        "assistant: تم تأكيد الحجز بنجاح.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمرحبا"
    )
    assert required_quality_tier(runtime_message) == 1


def test_system_policy_action_words_do_not_raise_simple_message():
    runtime_message = (
        "Never claim a booking or order succeeded.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمرحبا"
    )
    assert required_quality_tier(runtime_message) == 1
