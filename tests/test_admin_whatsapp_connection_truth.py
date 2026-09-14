from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_admin_channel_list_verifies_whatsapp_connection():
    api = source("backend/app/api/admin_channels.py")
    assert "whatsapp_connection_state" in api
    assert 'verify_connection=item.channel_type == "whatsapp"' in api
    assert '"connected": configured' in api
    assert '"connection_status"' in api


def test_whatsapp_activation_requires_verified_meta_connection_not_just_config():
    api = source("backend/app/api/admin_channels.py")
    blockers = api.split("def _activation_blockers", 1)[1].split("@router.post", 1)[0]
    assert 'channel.channel_type == "whatsapp"' in blockers
    assert "whatsapp_connection_state(" in blockers
    assert "verify_remote=True" in blockers
    assert 'connection["connected"] is not True' in blockers
    assert 'connection.get("connection_issue")' in blockers


def test_admin_ui_separates_configuration_activation_and_meta_connection():
    ui = source("frontend/admin/company-control-center.js")
    assert "Disconnected · Invalid token" in ui
    assert "Configured only" in ui
    assert "Local channel active" in ui
    assert "Credentials:" in ui
    assert "Connect with Meta" in ui
    assert "x.enabled===true&&x.connected===true" in ui


def test_admin_attention_panel_flags_locally_active_disconnected_whatsapp():
    ui = source("frontend/admin/control-center-polish.js")
    assert "channel.channel_type==='whatsapp'" in ui
    assert "channel.enabled" in ui
    assert "channel.connected!==true" in ui
    assert "WhatsApp connection needs attention" in ui
    assert "channel.connection_issue" in ui


def test_customer_status_surfaces_safe_meta_probe_failure():
    api = source("backend/app/api/customer_meta_whatsapp.py")
    ui = source("frontend/customer/meta-whatsapp.js")
    assert '"connection_status": connection["connection_status"]' in api
    assert '"connection_issue": connection["connection_issue"]' in api
    assert '"meta_error_code": connection["meta_error_code"]' in api
    assert 'config.connection_status === "invalid_token"' in ui
    assert "config.connection_issue" in ui
