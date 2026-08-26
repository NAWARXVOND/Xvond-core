from pathlib import Path

from backend.app.api import admin_meta_whatsapp


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_graph_url_is_pinned_to_meta_graph_host():
    url = admin_meta_whatsapp._graph_url("v23.0", "123/phone_numbers", {"fields": "id"})
    assert url.startswith("https://graph.facebook.com/v23.0/123/phone_numbers?")


def test_meta_completion_subscribes_waba_before_local_activation():
    api = source("backend/app/api/admin_meta_whatsapp.py")
    assert "_verify_phone_belongs_to_waba" in api
    assert "_subscribe_app_to_waba" in api
    assert 'f"{urllib.parse.quote(waba_id, safe=' in api
    assert '"webhook_subscribed": True' in api
    assert "_activation_blockers" in api
    assert "channel.enabled = not blockers" in api


def test_meta_signup_requires_complete_server_configuration_before_launch():
    api = source("backend/app/api/admin_meta_whatsapp.py")
    assert "_missing_meta_settings" in api
    assert 'for key in ("app_id", "app_secret", "config_id", "verify_token")' in api
    assert '"missing_settings": missing' in api


def test_meta_token_exchange_does_not_put_app_secret_in_query_string():
    api = source("backend/app/api/admin_meta_whatsapp.py")
    assert '"POST",\n        _graph_url(config["graph_api_version"], "oauth/access_token"),' in api
    assert "form=form" in api
    assert '"oauth/access_token", params' not in api


def test_meta_reconnect_preserves_existing_channel_behavior():
    api = source("backend/app/api/admin_meta_whatsapp.py")
    assert "WHATSAPP_BEHAVIOR_DEFAULTS" in api
    assert "if channel is None:\n            incoming.update(WHATSAPP_BEHAVIOR_DEFAULTS)" in api
    assert "validate_channel_config(\"whatsapp\", reveal_config(merged))" in api


def test_meta_browser_origin_check_is_not_suffix_only():
    js = source("frontend/admin/meta-whatsapp.js")
    assert "new URL(origin)" in js
    assert "h==='facebook.com'||h.endsWith('.facebook.com')" in js
    assert "event.origin.endsWith('facebook.com')" not in js


def test_modern_admin_loads_meta_signup_and_exposes_button():
    index = source("frontend/admin/index.html")
    company = source("frontend/admin/simple-company.js")
    assert "/static/admin/meta-whatsapp.js" in index
    assert "Connect WhatsApp with Meta" in company
    assert "openMetaWhatsAppConnect" in company


def test_meta_environment_template_contains_no_real_secrets():
    env = source(".env.example")
    assert "META_APP_ID=" in env
    assert "META_APP_SECRET=" in env
    assert "META_WHATSAPP_CONFIG_ID=" in env
    assert "META_WHATSAPP_VERIFY_TOKEN=" in env
