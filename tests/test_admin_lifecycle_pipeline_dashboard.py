from pathlib import Path


DASHBOARD_API = Path("backend/app/api/admin_dashboard.py").read_text(encoding="utf-8")
ADMIN_APP = Path("frontend/admin/app.js").read_text(encoding="utf-8")


def test_dashboard_api_reports_company_lifecycle_pipeline():
    assert "LIFECYCLE_ORDER" in DASHBOARD_API
    assert '"onboarding"' in DASHBOARD_API
    assert '"testing"' in DASHBOARD_API
    assert '"live"' in DASHBOARD_API
    assert '"paused"' in DASHBOARD_API
    assert '"suspended"' in DASHBOARD_API
    assert '"lifecycle_counts": lifecycle_counts' in DASHBOARD_API


def test_admin_dashboard_renders_customer_pipeline_counts():
    assert "data.lifecycle_counts" in ADMIN_APP
    assert '["Onboarding",adminNumber(lifecycle.onboarding)]' in ADMIN_APP
    assert '["Testing",adminNumber(lifecycle.testing)]' in ADMIN_APP
    assert '["Live",adminNumber(lifecycle.live)]' in ADMIN_APP
    assert '["Paused",adminNumber(lifecycle.paused)]' in ADMIN_APP
    assert '["Suspended",adminNumber(lifecycle.suspended)]' in ADMIN_APP
