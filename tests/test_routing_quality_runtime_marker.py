from backend.app.core.ai.routing_quality import required_quality_tier


def test_system_prompt_action_words_do_not_raise_simple_message():
    message = (
        "Never claim a booking, order, cancellation, reschedule, payment or other action succeeded.\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nhello"
    )
    assert required_quality_tier(message) == 1
