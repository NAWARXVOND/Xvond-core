import inspect
from pathlib import Path

from backend.app.api import customer_inbox


def test_customer_inbox_exposes_human_handoff_actions():
    source = inspect.getsource(customer_inbox)
    assert '@router.post("/{conversation_id}/take-over")' in source
    assert '@router.post("/{conversation_id}/return-ai")' in source
    assert '@router.post("/{conversation_id}/message")' in source
    assert "require_customer_manager" in source
    assert "resume_ai(session)" in source
    assert 'AIMessage(conversation_id=conversation.id, role="human"' in source


def test_customer_inbox_returns_current_mode():
    source = inspect.getsource(customer_inbox._conversation_meta)
    assert '"mode": handoff["mode"]' in source
    assert '"handoff_status": handoff["handoff_status"]' in source


def test_customer_inbox_orders_by_latest_message_activity():
    source = inspect.getsource(customer_inbox.list_inbox)
    assert "func.max(AIMessage.id)" in source
    assert "latest_message_id.desc().nullslast()" in source
    assert "AIConversation.id.desc()" in source


def test_customer_portal_takeover_does_not_fake_a_human_message_timestamp():
    source = inspect.getsource(customer_inbox.take_over_conversation)
    assert "activate_human_handoff(" in source
    assert "human_message=True" not in source


def test_customer_inbox_audits_handoff_lifecycle_without_message_content():
    source = inspect.getsource(customer_inbox)
    assert 'action="customer_inbox.handoff_started"' in source
    assert 'action="customer_inbox.ai_resumed"' in source
    assert 'action="customer_inbox.human_reply_sent"' in source
    audit_helper = inspect.getsource(customer_inbox._audit_handoff)
    assert 'resource_type="conversation"' in audit_helper
    assert '"external_contact_id"' in audit_helper
    assert '"content"' not in audit_helper


def test_human_reply_is_recorded_only_after_whatsapp_delivery_succeeds():
    source = inspect.getsource(customer_inbox.send_human_reply)
    send_position = source.index("whatsapp_sender.send_text")
    success_check_position = source.index('if not result.get("success")')
    message_position = source.index('AIMessage(conversation_id=conversation.id, role="human"')
    assert send_position < success_check_position < message_position
    assert "WhatsApp delivery failed; the reply was not recorded as sent" in source


def test_return_to_ai_completes_handoffs_and_resumes_session():
    source = inspect.getsource(customer_inbox.return_conversation_to_ai)
    completed_position = source.index('handoff.status = "completed"')
    resume_position = source.index("resume_ai(session)")
    assert completed_position < resume_position


def test_customer_portal_loads_handoff_ui():
    index = Path("frontend/customer/index.html").read_text(encoding="utf-8")
    ui = Path("frontend/customer/handoff-inbox.js").read_text(encoding="utf-8")
    assert "/static/customer/handoff-inbox.js" in index
    assert "Return to AI" in ui
    assert "Take Over" in ui
    assert "/return-ai" in ui
    assert "/take-over" in ui
    assert "/message" in ui


def test_customer_inbox_live_refresh_preserves_composer_until_thread_changes():
    ui = Path("frontend/customer/handoff-inbox.js").read_text(encoding="utf-8")
    assert "startInboxLiveRefresh" in ui
    assert "2500" in ui
    assert "activeInboxFingerprint" in ui
    assert "fingerprint === activeInboxFingerprint" in ui
    assert "preserveThread: true" in ui
