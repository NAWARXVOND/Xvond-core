from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_service_billing_is_the_canonical_customer_portal_source():
    portal = open("backend/app/api/customer_portal.py", encoding="utf-8").read()
    customer = open("frontend/customer/app.js", encoding="utf-8").read()
    assert "ServiceSubscription" in portal
    assert "ServicePlan" in portal
    assert '"services": services' in portal
    assert "service_limits.used" in portal
    assert "serviceByCode" in customer
    assert "serviceUsageMarkup" in customer


def test_service_limits_are_enforced_at_runtime_boundaries():
    runtime = open("backend/app/core/agent_runtime.py", encoding="utf-8").read()
    channels = open("backend/app/api/admin_channels.py", encoding="utf-8").read()
    employees = open("backend/app/api/admin_ai_employee_profile.py", encoding="utf-8").read()
    assert "assert_company_runtime_access" in runtime
    assert "limits_service.check_token_limit" in runtime
    assert "limits_service.check_channel_limit" in channels
    assert "limits_service.check_agent_limit" not in employees.split('@router.post("/companies/{company_id}")', 1)[1].split('@router.get("/companies/{company_id}/{agent_id}")', 1)[0]


def test_service_plan_management_is_admin_only():
    source = open("backend/app/api/admin_service_plan_management.py", encoding="utf-8").read()
    assert "require_xvond_admin" in source
    assert 'prefix="/admin/service-plans"' in source


def test_service_billing_customer_access_is_read_only():
    customer_portal = open("backend/app/api/customer_portal.py", encoding="utf-8").read()
    customer_app = open("frontend/customer/app.js", encoding="utf-8").read()
    assert '@router.get("/overview")' in customer_portal
    assert 'method: "POST"' not in customer_app.split("function renderBilling", 1)[1].split("async function startPortal", 1)[0]


def test_admin_workspace_exposes_service_billing_management():
    source = open("frontend/admin/company-control-center.js", encoding="utf-8").read()
    assert "Service Billing" in source
    assert "/admin/service-billing/companies/" in source
    assert "Assign Service Plan" in source


def test_customer_portal_has_service_driven_navigation():
    source = open("backend/app/modules/solutions/portal.py", encoding="utf-8").read()
    assert "SERVICE_PORTAL_REGISTRY" in source
    assert "build_customer_portal_navigation" in source
    assert '"ai_agents"' in source
    assert '"automation"' in source
    assert '"analytics"' in source
    assert '"integrations"' in source


def test_service_plan_admin_ui_has_supported_limit_fields():
    source = open("frontend/admin/billing-plan-management.js", encoding="utf-8").read()
    assert "['agents', 'AI Employees']" in source
    assert "['channels', 'Active Channels']" in source
    assert "['tokens', 'AI tokens / month']" in source
    assert "['requests', 'AI requests / month']" in source


def test_channel_capacity_is_consumed_on_activation_not_disabled_creation():
    source = open("backend/app/api/admin_channels.py", encoding="utf-8").read()
    creation_block = source.split('@router.post("/agents/{agent_id}")', 1)[1].split('@router.get("/companies/{company_id}")', 1)[0]
    activation_block = source.split('@router.put("/{channel_id}")', 1)[1].split('@router.put("/{channel_id}/whatsapp-config")', 1)[0]
    assert "check_channel_limit" not in creation_block
    assert "limits_service.check_channel_limit" in activation_block


def test_ai_employee_capacity_is_consumed_on_go_live_not_draft_creation():
    admin_source = open("backend/app/api/admin_ai_employee_profile.py", encoding="utf-8").read()
    delivery_source = open("backend/app/api/admin_delivery_readiness.py", encoding="utf-8").read()
    customer_source = open("backend/app/api/customer_agents.py", encoding="utf-8").read()
    creation_block = admin_source.split('@router.post("/companies/{company_id}")', 1)[1].split('@router.get("/companies/{company_id}/{agent_id}")', 1)[0]
    assert "limits_service.check_agent_limit" not in creation_block
    assert "enabled=False" in creation_block
    assert "limits_service.check_agent_limit(db, company_id)" in delivery_source
    assert "limits_service.check_agent_limit(db, current_user.company_id)" in customer_source
    assert "Depends(require_customer_manager)" in customer_source


def test_whatsapp_and_voice_have_customer_safe_service_limit_fallbacks():
    whatsapp = open("backend/app/api/whatsapp_webhook.py", encoding="utf-8").read()
    voice = open("backend/app/api/voice_llm.py", encoding="utf-8").read()
    assert "whatsapp.customer_service_fallback" in whatsapp
    assert "is_service_access_error" in whatsapp
    assert "_voice_service_fallback" in voice
