from backend.app.core.ai.routing_quality import required_quality_tier


def test_arabic_action_detail_followup_stays_standard():
    message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: بدي احجز موعد بكرا\n"
        "assistant: أكيد، شو الاسم ورقم الهاتف؟\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nمحمد"
    )
    assert required_quality_tier(message) == 2


def test_english_action_detail_followup_stays_standard():
    message = (
        "CONVERSATION HISTORY (use for continuity; not authoritative for business facts):\n"
        "user: I want to book an appointment\n"
        "assistant: What name and phone number should I use?\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nNawar"
    )
    assert required_quality_tier(message) == 2
