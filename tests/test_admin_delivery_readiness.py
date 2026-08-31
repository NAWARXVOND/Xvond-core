from pathlib import Path


READINESS = Path("backend/app/api/admin_delivery_readiness.py").read_text(encoding="utf-8")
MAIN = Path("backend/app/main.py").read_text(encoding="utf-8")


def test_delivery_readiness_route_is_registered():
    assert 'prefix="/admin/delivery-readiness"' in READINESS
    assert '@router.get("/companies/{company_id}/agents/{agent_id}")' in READINESS
    assert "from backend.app.api.admin_delivery_readiness import router as admin_delivery_readiness_router" in MAIN
    assert "admin_delivery_readiness_router," in MAIN


def test_conversational_employee_does_not_require_actions_or_workflow_engine():
    assert '"requested": False' in READINESS
    assert '"ready": True' in READINESS
    assert '"requires_workflow_engine": False' in READINESS
    assert '"mode": "conversational_and_operational" if actions["requested"] else "conversational"' in READINESS


def test_operational_employee_requires_workflow_and_configured_integrations():
    assert '"requires_workflow_engine": bool(enabled_actions)' in READINESS
    assert "Workflow Engine is not ready for enabled business actions" in READINESS
    assert "Connected App #" in READINESS
    assert "N8N_SHARED_SECRET" in READINESS


def test_readiness_checks_customer_delivery_basics():
    for value in (
        "employee_enabled",
        "profile",
        "knowledge",
        "channels",
        "actions",
        "workflow_engine",
        "connected_apps",
        "ready_for_customer",
    ):
        assert value in READINESS
