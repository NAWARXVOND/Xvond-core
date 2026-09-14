from pathlib import Path


LIFECYCLE = Path("backend/app/core/company_lifecycle.py").read_text(encoding="utf-8")
ADMIN = Path("backend/app/api/admin.py").read_text(encoding="utf-8")
PRODUCTION = Path("backend/app/api/admin_production.py").read_text(encoding="utf-8")
PRIVACY_UI = Path("frontend/admin/privacy-boundaries.js").read_text(encoding="utf-8")


def _activation_block():
    return LIFECYCLE.split("def activate_company(", 1)[1].split(
        "def deactivate_company(", 1
    )[0]


def test_company_activation_does_not_enable_ai_employees():
    block = _activation_block()
    assert "company.active = True" in block
    assert "AIAgent.enabled: True" not in block
    assert ".update(" not in block


def test_company_activation_documents_employee_lifecycle_authority():
    assert "Employee Go Live" in LIFECYCLE
    assert "does not enable AI employees" in LIFECYCLE
    assert "Delivery Readiness" in PRODUCTION
    assert "must never enable employees" in PRODUCTION


def test_company_deactivation_remains_emergency_stop():
    deactivation = LIFECYCLE.split("def deactivate_company(", 1)[1]
    assert "company.active = False" in deactivation
    assert "AIAgent.enabled: False" in deactivation


def test_admin_and_legacy_production_routes_share_lifecycle_service():
    assert "activate_company(db, company_id)" in ADMIN
    assert "deactivate_company(db, company_id)" in ADMIN
    assert "activate_company_state(db, company_id)" in PRODUCTION
    assert "deactivate_company_state(db, company_id)" in PRODUCTION
    assert "status_code=409" in ADMIN
    assert "status_code=409" in PRODUCTION


def test_admin_ui_calls_canonical_company_status_endpoint():
    assert "/admin/companies/${xvondWorkspace.companyId}/status" in PRIVACY_UI
    canonical = PRIVACY_UI.split("toggleCanonicalWorkspaceCompany", 1)[1].split(
        "renderCompanyControlCenter", 1
    )[0]
    assert "/admin/production/" not in canonical
