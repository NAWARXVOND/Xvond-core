from pathlib import Path


def test_admin_ui_uses_ai_employee_profile_editor_only():
    app = Path("frontend/admin/app.js").read_text(encoding="utf-8")
    profile = Path("frontend/admin/employee-capabilities.js").read_text(encoding="utf-8")

    assert "openEditAgent" not in app
    assert "saveAgentEdit" not in app
    assert "agent-factory" not in app
    assert "openEditAIEmployee" in profile
    assert "/admin/ai-employee-profile/companies/" in profile


def test_generic_admin_ai_api_is_diagnostics_only():
    source = Path("backend/app/api/admin_ai.py").read_text(encoding="utf-8-sig")

    assert "test-chat" in source
    assert '@router.get("/ai/providers")' in source
    assert "AIAgentCreate" not in source
    assert "AIAgentUpdate" not in source
    assert '@router.put(' not in source
    assert 'custom-agent' not in source
