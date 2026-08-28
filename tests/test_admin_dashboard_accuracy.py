from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCURACY_JS = ROOT / "frontend" / "admin" / "dashboard-accuracy.js"
INDEX_HTML = ROOT / "frontend" / "admin" / "index.html"


def test_admin_accuracy_layer_is_loaded_last():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert '/static/admin/dashboard-accuracy.js' in html
    assert html.rfind('/static/admin/dashboard-accuracy.js') > html.rfind('/static/admin/billing-plan-management.js')


def test_employee_channel_count_uses_enabled_channels_only():
    source = ACCURACY_JS.read_text(encoding="utf-8")
    assert "x.enabled===true" in source
    assert "Active Channels" in source


def test_connected_readiness_requires_configured_and_enabled_channel():
    source = ACCURACY_JS.read_text(encoding="utf-8")
    assert "x.enabled===true&&x.configured===true" in source


def test_billing_surfaces_reached_and_exceeded_limits():
    source = ACCURACY_JS.read_text(encoding="utf-8")
    assert "Limit exceeded" in source
    assert "Limit reached" in source


def test_unimplemented_notification_destinations_are_not_presented_as_live():
    source = ACCURACY_JS.read_text(encoding="utf-8")
    assert "Not connected" in source
    assert "Dashboard delivery is active." in source
