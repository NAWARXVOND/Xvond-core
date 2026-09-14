from pathlib import Path


CUSTOMER_PORTAL = Path("backend/app/api/customer_portal.py").read_text(encoding="utf-8")
CUSTOMER_INDEX = Path("frontend/customer/index.html").read_text(encoding="utf-8")
LIFECYCLE_BANNER = Path("frontend/customer/company-lifecycle-banner.js").read_text(encoding="utf-8")


def test_customer_overview_exposes_lifecycle_without_internal_controls():
    assert '"lifecycle_status": company.lifecycle_status' in CUSTOMER_PORTAL
    assert '"lifecycle_updated_at": company.lifecycle_updated_at' in CUSTOMER_PORTAL
    assert "_company_portal_state(company)" in CUSTOMER_PORTAL


def test_customer_portal_loads_lifecycle_banner():
    assert "/static/customer/company-lifecycle-banner.js" in CUSTOMER_INDEX
    assert "Company status" in LIFECYCLE_BANNER
    assert "AI Runtime" in LIFECYCLE_BANNER
    assert "Onboarding" in LIFECYCLE_BANNER
    assert "Testing" in LIFECYCLE_BANNER
    assert "Live" in LIFECYCLE_BANNER


def test_customer_lifecycle_banner_is_read_only():
    assert "/customer/overview" in LIFECYCLE_BANNER
    assert "/admin/companies/" not in LIFECYCLE_BANNER
    assert "setWorkspaceLifecycle" not in LIFECYCLE_BANNER
