from pathlib import Path


def test_admin_ui_contains_live_agent_test_chat():
    script = Path("frontend/admin/app.js").read_text(encoding="utf-8")

    assert "openAgentTestChat" in script
    assert "sendAgentTestMessage" in script
    assert "/test-chat" in script
    assert "conversation_id: agentTestConversationId" in script
    assert "escapeAdmin(result.response.content)" in script
