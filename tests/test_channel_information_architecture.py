from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_whatsapp_channel_does_not_duplicate_employee_language_or_dialect():
    ui = read("frontend/admin/simple-company.js")
    assert 'id="simple-wa-language"' not in ui
    assert 'id="simple-wa-dialect"' not in ui
    assert "Reply language and dialect come from the AI Employee profile" in ui
    assert "WhatsApp-only Instructions" in ui


def test_voice_channel_separates_transport_language_from_employee_language():
    ui = read("frontend/admin/voice-admin.js")
    assert 'id="voice-dialect"' not in ui
    assert "Speech Recognition Language" in ui
    assert "does not override the employee's reply-language policy" in ui
    assert "Human takeover" in ui
    assert "Not connected" in ui


def test_customer_employee_cards_explain_shared_brain_across_channels():
    ui = read("frontend/customer/agent-channel-status.js")
    assert "Customer Channels" in ui
    assert "The same employee identity, knowledge and allowed actions are used across these channels." in ui
    assert "Live" in ui
    assert "Inactive" in ui


def test_customer_business_profile_is_company_level_not_employee_level():
    index = read("frontend/customer/index.html")
    ia = read("frontend/customer/portal-information-architecture.js")
    assert 'id="page-business-profile"' in index
    assert "The single source of truth for company facts shared with every AI employee" in index
    assert "Company Identity" in ia
    assert "Region & Language" in ia
    assert "Working Hours" in ia
    assert "Open Business Profile" in ia
    assert "button.remove()" in ia


def test_admin_is_not_a_customer_conversation_control_plane():
    simple = read("frontend/admin/simple-company.js")
    privacy = read("frontend/admin/privacy-boundaries.js")
    assert "takeOverConversation" not in simple
    assert "returnConversationToAI" not in simple
    assert "Customer-created content is intentionally not loaded into Admin." in privacy
    assert "requests: []" in privacy
    assert "conversations: []" in privacy
    assert "handoffs: []" in privacy
