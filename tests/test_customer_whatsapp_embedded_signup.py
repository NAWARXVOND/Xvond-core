from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_customer_whatsapp_routes_are_tenant_scoped_and_manager_only():
    api = source("backend/app/api/customer_meta_whatsapp.py")
    assert "require_customer_manager" in api
    assert "AIAgent.company_id == current_user.company_id" in api
    assert 'prefix="/customer/meta/whatsapp"' in api
    assert '"app_secret"' not in api.split('return {', 1)[1].split('}', 1)[0]


def test_customer_whatsapp_completion_reuses_secure_meta_flow():
    api = source("backend/app/api/customer_meta_whatsapp.py")
    assert "_exchange_code_for_token" in api
    assert "_resolve_signup_phone" in api
    assert "_subscribe_app_to_waba" in api
    assert "validate_channel_config" in api
    assert "channel.enabled = not blockers" in api
    assert 'action="whatsapp.customer_embedded_signup.connected"' in api


def test_customer_agent_router_includes_whatsapp_signup_router():
    api = source("backend/app/api/customer_agents.py")
    assert "customer_meta_whatsapp_router" in api
    assert "router.include_router(customer_meta_whatsapp_router)" in api


def test_customer_portal_loads_meta_signup_ui():
    index = source("frontend/customer/index.html")
    js = source("frontend/customer/meta-whatsapp.js")
    assert "/static/customer/meta-whatsapp.js" in index
    assert "Connect WhatsApp" in js
    assert "/customer/meta/whatsapp/embedded-signup/config" in js
    assert "/customer/meta/whatsapp/embedded-signup/complete" in js
    assert "featureType: \"whatsapp_business_app_onboarding\"" in js


def test_customer_meta_origin_validation_is_strict():
    js = source("frontend/customer/meta-whatsapp.js")
    assert "new URL(origin)" in js
    assert 'host === "facebook.com" || host.endsWith(".facebook.com")' in js
    assert "event.origin.endsWith('facebook.com')" not in js
