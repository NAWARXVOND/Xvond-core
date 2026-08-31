from pathlib import Path


ADMIN = Path("backend/app/api/admin.py").read_text(encoding="utf-8")
DELIVERY = Path("backend/app/api/admin_delivery_readiness.py").read_text(encoding="utf-8")
READINESS = Path("backend/app/core/readiness.py").read_text(encoding="utf-8")
MAIN = Path("backend/app/main.py").read_text(encoding="utf-8")
BOOTSTRAP = Path("backend/app/modules/tools/bootstrap.py").read_text(encoding="utf-8")


def test_company_activation_is_readiness_gated_and_deactivation_is_emergency_stop():
    assert "readiness = company_readiness(db, company_id)" in ADMIN
    assert 'if not readiness["ready"]' in ADMIN
    assert "Company is not ready to activate" in ADMIN
    assert "AIAgent.enabled: False" in ADMIN


def test_company_setup_readiness_uses_configured_not_live_channels():
    assert ".filter(AgentChannel.agent_id == agent.id)" in READINESS
    assert "configured_channels =" in READINESS
    assert "live_channels =" in READINESS
    assert '"setup_ready": setup_ready' in READINESS
    assert '"ready_for_customer": ready_for_customer' in READINESS
    assert "and configured_channels" in READINESS


def test_employee_go_live_requires_active_company_and_customer_ready_requires_all_gates():
    assert "Activate the company before the AI employee goes live" in DELIVERY
    assert '"company_active": bool(company.active)' in DELIVERY
    assert "company.active and agent.enabled and setup_ready and channels[\"live\"]" in DELIVERY


def test_delivery_readiness_is_only_registered_at_its_canonical_prefix():
    assert "admin_delivery_readiness_router" in MAIN
    assert "delivery_readiness_router" not in ADMIN
    assert 'prefix="/admin/delivery-readiness"' in DELIVERY


def test_only_workflow_backed_action_tool_is_registered():
    assert "workflow_action_request_tool" in BOOTSTRAP
    assert "action_request_tool" not in BOOTSTRAP.replace("workflow_action_request_tool", "")


def test_unreachable_duplicate_company_admin_module_is_removed():
    assert not Path("backend/app/api/admin_companies.py").exists()
