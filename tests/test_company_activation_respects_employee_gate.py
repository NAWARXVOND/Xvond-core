from pathlib import Path


PRODUCTION = Path("backend/app/api/admin_production.py").read_text(encoding="utf-8")


def _activation_block():
    return PRODUCTION.split('def activate_company(', 1)[1].split('@router.post(\n    "/companies/{company_id}/deactivate"', 1)[0]


def test_company_activation_does_not_enable_ai_employees():
    block = _activation_block()
    assert "company.active = True" in block
    assert "AIAgent.enabled: True" not in block
    assert ".update(" not in block


def test_company_activation_documents_employee_lifecycle_authority():
    assert "AI employee lifecycle is owned exclusively by the Delivery Readiness" in PRODUCTION
    assert "must never enable employees as a side" in PRODUCTION


def test_company_deactivation_remains_emergency_stop():
    deactivation = PRODUCTION.split('def deactivate_company(', 1)[1]
    assert "company.active = False" in deactivation
    assert "AIAgent.enabled:" in deactivation
    assert "False" in deactivation
