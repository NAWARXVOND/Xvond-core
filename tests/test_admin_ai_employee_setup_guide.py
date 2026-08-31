from pathlib import Path


GUIDE = Path("frontend/admin/ai-employee-setup-guide.js").read_text(encoding="utf-8")
INDEX = Path("frontend/admin/index.html").read_text(encoding="utf-8")
PROFILE_API = Path("backend/app/api/admin_ai_employee_profile.py").read_text(encoding="utf-8")


def test_admin_loads_ai_employee_setup_guide():
    assert "/static/admin/ai-employee-setup-guide.js" in INDEX
    assert "Setup Guide" in GUIDE
    assert "Business knowledge" in GUIDE
    assert "Allowed business actions" in GUIDE
    assert "Customer channels" in GUIDE
    assert "Connected apps for execution" in GUIDE
    assert "Workflow Engine" in GUIDE


def test_setup_guide_keeps_execution_authority_in_workflow_engine():
    assert "Business side effects are executed only through the Workflow Engine" in GUIDE
    assert "operation succeeded until execution returns success" in GUIDE


def test_employee_creation_keeps_one_canonical_profile_endpoint():
    assert '@router.post("/companies/{company_id}")' in PROFILE_API
    assert "create_profile_employee" in PROFILE_API
    assert "_select_model(db, company_id)" in PROFILE_API
    assert 'for module_name in ("ai_agent", "knowledge", "tools")' in PROFILE_API


def test_vendor_name_is_not_exposed_by_setup_guide():
    assert "n8n" not in GUIDE.lower()
