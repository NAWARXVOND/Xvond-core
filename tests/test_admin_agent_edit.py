from pathlib import Path


def test_admin_ui_contains_agent_edit_workflow():
    script = Path("frontend/admin/app.js").read_text(encoding="utf-8")

    assert "openEditAgent" in script
    assert "saveAgentEdit" in script
    assert "edit-agent-provider" in script
    assert "edit-agent-model" in script
    assert "edit-agent-prompt" in script


def test_agent_list_exposes_prompt_for_editor():
    source = Path("backend/app/api/admin_ai.py").read_text(encoding="utf-8")

    assert '"system_prompt": agent.system_prompt' in source
    assert '@router.put(' in source
    assert '"/companies/{company_id}/agents/{agent_id}"' in source
