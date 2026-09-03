from datetime import datetime, timedelta
from types import SimpleNamespace

from backend.app.api.whatsapp_webhook import (
    _business_app_echo_content,
    _business_app_echo_created_at,
)
from backend.app.modules.channels.handoff import (
    activate_human_handoff,
    human_handoff_active,
    resume_ai,
)


def test_business_app_text_echo_preserves_message_body():
    echo = {
        "type": "text",
        "text": {"body": "Manual reply from WhatsApp Business"},
    }

    assert _business_app_echo_content(echo) == "Manual reply from WhatsApp Business"


def test_business_app_media_echo_preserves_caption_or_uses_safe_label():
    captioned = {
        "type": "image",
        "image": {"caption": "Product photo"},
    }
    audio = {"type": "audio", "audio": {"id": "media-id"}}

    assert _business_app_echo_content(captioned) == "Product photo"
    assert _business_app_echo_content(audio) == "[Audio sent from WhatsApp Business]"


def test_business_app_echo_timestamp_is_normalized_to_utc_naive_datetime():
    echo = {"timestamp": "1700000000"}

    assert _business_app_echo_created_at(echo) == datetime.utcfromtimestamp(1700000000)
    assert _business_app_echo_created_at({"timestamp": "bad"}) is None


def test_human_takeover_does_not_expire_until_explicit_resume():
    old_deadline = datetime.utcnow() - timedelta(hours=4)
    session = SimpleNamespace(
        automation_state="ai",
        handoff_reason=None,
        human_takeover_until=old_deadline,
        updated_at=None,
        last_human_message_at=None,
    )

    activate_human_handoff(
        session,
        reason="business_app_reply",
        human_message=True,
    )

    assert session.automation_state == "human"
    assert session.human_takeover_until is None
    assert session.last_human_message_at is not None
    assert human_handoff_active(session, now=datetime.utcnow() + timedelta(days=7)) is True

    resume_ai(session)

    assert session.automation_state == "ai"
    assert session.handoff_reason is None
    assert human_handoff_active(session) is False
