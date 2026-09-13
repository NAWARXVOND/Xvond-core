from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.core.dependencies import require_customer_user
from backend.app.main import app


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


def test_customer_whatsapp_routes_match_portal_urls():
    paths = app.openapi()["paths"]
    prefix = "/customer/meta/whatsapp/embedded-signup"
    assert "get" in paths.get(f"{prefix}/config", {})
    assert "post" in paths.get(f"{prefix}/complete", {})
    assert not any(path.startswith("/customer/agents/customer/meta/") for path in paths)


@pytest.mark.parametrize("method, endpoint", [("GET", "config?agent_id=7"), ("POST", "complete")])
def test_customer_whatsapp_routes_require_authentication(method, endpoint):
    response = TestClient(app).request(
        method, f"/customer/meta/whatsapp/embedded-signup/{endpoint}"
    )
    assert response.status_code == 401


@pytest.mark.parametrize("method, endpoint", [("GET", "config?agent_id=7"), ("POST", "complete")])
def test_customer_whatsapp_routes_forbid_staff(monkeypatch, method, endpoint):
    monkeypatch.setitem(
        app.dependency_overrides,
        require_customer_user,
        lambda: SimpleNamespace(role="employee", company_id=7),
    )
    response = TestClient(app).request(
        method, f"/customer/meta/whatsapp/embedded-signup/{endpoint}"
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Company management access required"


def test_customer_portal_loads_meta_signup_ui():
    index = source("frontend/customer/index.html")
    js = source("frontend/customer/meta-whatsapp.js")
    assert "/static/customer/meta-whatsapp.js" in index
    assert "ربط WhatsApp" in js
    assert "/customer/meta/whatsapp/embedded-signup/config" in js
    assert "/customer/meta/whatsapp/embedded-signup/complete" in js
    assert "xvondCustomerMetaLoginOptions" in js
    assert "if (config.feature_type) extras.featureType = config.feature_type" in js
    assert "if (config.session_info_version) extras.sessionInfoVersion" in js


def test_customer_connection_status_requires_real_meta_onboarding():
    api = source("backend/app/api/customer_meta_whatsapp.py")
    assert "_META_CONNECTION_METHODS" in api
    assert "whatsapp_meta_onboarding_complete" in api
    assert "whatsapp_connection_state(channel_config, verify_remote=True)" in api
    assert '"connected": connected' in api
    assert '"connection_status": connection["connection_status"]' in api
    assert '"connection_issue": connection["connection_issue"]' in api


def test_customer_whatsapp_status_exposes_runtime_readiness_and_blockers():
    api = source("backend/app/api/customer_meta_whatsapp.py")
    js = source("frontend/customer/meta-whatsapp.js")
    assert "blockers = _activation_blockers(db, channel)" in api
    assert '"runtime_ready": bool(connected and enabled and not blockers)' in api
    assert '"blockers": blockers' in api
    assert '"coexistence": bool(channel_config.get("coexistence"))' in api
    assert "xvondCustomerWhatsAppStatus" in js
    assert "xvondCustomerWhatsAppBlockers" in js
    assert "config.runtime_ready" in js
    assert "config.coexistence" in js


def test_customer_meta_origin_validation_is_strict():
    js = source("frontend/customer/meta-whatsapp.js")
    assert "new URL(origin)" in js
    assert 'host === "facebook.com" || host.endsWith(".facebook.com")' in js
    assert "event.origin.endsWith('facebook.com')" not in js
