from pathlib import Path


def test_admin_ui_contains_live_ai_employee_test_chat():
    script = Path("frontend/admin/app.js").read_text(encoding="utf-8")

    assert "openAgentTestChat" in script
    assert "sendAgentTestMessage" in script
    assert "/test-chat" in script
    assert "conversation_id:agentTestConversationId" in script.replace(" ", "")
    assert "result.response?.content" in script
    assert "AI Employee" in script
