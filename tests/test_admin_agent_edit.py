from pathlib import Path

from backend.app.main import app


def test_admin_agent_detail_route_exists():
    routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert (
        "GET",
        "/admin/companies/{company_id}/agents/{agent_id}",
    ) in routes
    assert (
        "PUT",
        "/admin/companies/{company_id}/agents/{agent_id}",
    ) in routes


def test_admin_ui_contains_agent_edit_workflow():
    script = Path("frontend/admin/app.js").read_text(encoding="utf-8")

    assert "openEditAgent" in script
    assert "saveAgentEdit" in script
    assert "edit-agent-provider" in script
    assert "edit-agent-model" in script
    assert "edit-agent-prompt" in script
