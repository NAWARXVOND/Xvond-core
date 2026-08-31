from pathlib import Path


ADMIN_API = Path("backend/app/api/admin.py").read_text(encoding="utf-8")
ADMIN_INDEX = Path("frontend/admin/index.html").read_text(encoding="utf-8")
WORKFLOW_UI = Path("frontend/admin/workflow-engine-admin.js").read_text(encoding="utf-8")


def test_admin_exposes_generic_workflow_engine_status():
    assert '@router.get("/workflow-engine/status")' in ADMIN_API
    assert '"status": status' in ADMIN_API
    assert '"configured": configured' in ADMIN_API


def test_admin_loads_workflow_engine_workspace_ui():
    assert '/static/admin/workflow-engine-admin.js' in ADMIN_INDEX
    assert 'Workflow Engine' in WORKFLOW_UI
    assert 'Connected Apps' in WORKFLOW_UI
    assert '/admin/workflow-engine/status' in WORKFLOW_UI


def test_admin_ui_does_not_expose_workflow_vendor_name():
    assert "n8n" not in WORKFLOW_UI.lower()
