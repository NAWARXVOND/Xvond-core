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


def test_readiness_separates_setup_ready_from_live_customer_state():
    assert '"setup_ready": setup_ready' in READINESS
    assert '"ready_for_customer": ready_for_customer' in READINESS
    assert 'company.active and agent.enabled and setup_ready and channels["live"]' in READINESS
    assert '"lifecycle": "live" if agent.enabled else "draft"' in READINESS
    assert 'blockers.insert(0, "AI employee is in draft mode")' in READINESS
    assert '"company_active": bool(company.active)' in READINESS


def test_draft_can_be_setup_with_configured_channel_before_channel_activation():
    assert "def _channel_state" in READINESS
    assert '"configured": bool(configured)' in READINESS
    assert '"live": bool(live)' in READINESS
    assert 'if not channels["configured"]' in READINESS
    assert 'setup_blockers.append("Connect and configure at least one customer channel")' in READINESS
    assert 'elif not channels["live"]' in READINESS
    assert 'blockers.append("Activate at least one customer channel")' in READINESS


def test_go_live_is_guarded_by_setup_company_state_and_plan_capacity():
    assert '@router.post("/companies/{company_id}/agents/{agent_id}/go-live")' in READINESS
    assert 'if not state["payload"]["setup_ready"]' in READINESS
    assert "Activate the company before the AI employee goes live" in READINESS
    assert "limits_service.check_agent_limit(db, company_id)" in READINESS
    assert "agent.enabled = True" in READINESS
    assert '@router.post("/companies/{company_id}/agents/{agent_id}/deactivate")' in READINESS


def test_readiness_checks_customer_delivery_basics():
    for value in (
        "company_active",
        "employee_enabled",
        "profile",
        "knowledge",
        "channels",
        "live_channels",
        "actions",
        "workflow_engine",
        "connected_apps",
        "ready_for_customer",
        "setup_ready",
    ):
        assert value in READINESS
