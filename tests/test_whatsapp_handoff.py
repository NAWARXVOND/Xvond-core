from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from backend.app.modules.channels.handoff import (
    activate_human_handoff,
    echo_recipient,
    human_handoff_active,
    requests_human,
    resume_ai,
)


def make_session():
    return SimpleNamespace(
        automation_state="ai",
        handoff_reason=None,
        human_takeover_until=None,
        last_human_message_at=None,
        updated_at=None,
    )


def test_customer_can_request_human_in_arabic_or_english():
    assert requests_human("بدي احكي مع موظف لو سمحت") is True
    assert requests_human("Can I speak with a human?") is True
    assert requests_human("شو أوقات الدوام؟") is False


def test_business_app_reply_activates_explicit_handoff():
    now = datetime(2026, 8, 24, 12, 0, 0)
    session = make_session()

    activate_human_handoff(
        session,
        reason="business_app_reply",
        now=now,
        minutes=45,
        human_message=True,
    )

    assert session.automation_state == "human"
    assert session.handoff_reason == "business_app_reply"
    assert session.last_human_message_at == now
    assert session.human_takeover_until is None
    assert human_handoff_active(
        session,
        now=now + timedelta(days=7),
    ) is True


def test_handoff_only_resumes_ai_explicitly():
    now = datetime(2026, 8, 24, 12, 0, 0)
    session = make_session()
    session.automation_state = "human"
    session.handoff_reason = "customer_request"
    session.human_takeover_until = now - timedelta(seconds=1)

    assert human_handoff_active(session, now=now) is True
    assert session.automation_state == "human"
    assert session.handoff_reason == "customer_request"

    resume_ai(session, now=now)

    assert session.automation_state == "ai"
    assert session.handoff_reason is None
    assert session.human_takeover_until is None


def test_echo_recipient_uses_customer_destination_only():
    assert echo_recipient({"to": "96890000000"}) == "96890000000"
    assert echo_recipient({"recipient_id": "96891111111"}) == "96891111111"
    assert echo_recipient({"from": "business-number"}) is None


def test_webhook_supports_meta_coexistence_echoes():
    source = Path(
        "backend/app/api/whatsapp_webhook.py"
    ).read_text(encoding="utf-8")

    assert '"smb_message_echoes"' in source
    assert "process_business_app_echo" in source
    assert "whatsapp_business_app" in source
