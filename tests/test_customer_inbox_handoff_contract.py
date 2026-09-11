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
