from pathlib import Path


API = Path("backend/app/api/admin_service_billing.py").read_text(encoding="utf-8")
UI = Path("frontend/admin/billing-plan-management.js").read_text(encoding="utf-8")
POLISH = Path("frontend/admin/control-center-polish.js").read_text(encoding="utf-8")


def test_admin_package_editor_has_a_real_backend_route():
    assert "@router.patch(\"/plans/{plan_id}\")" in API
    assert "def update_plan(" in API
    assert "data.model_dump(exclude_unset=True)" in API
    assert "Service plan not found" in API
    assert "service_plan.updated" in API
    assert "`/admin/service-billing/plans/${planId}`" in UI


def test_global_package_catalog_is_not_presented_as_company_local_configuration():
    assert "Global Package Catalog" in POLISH
    assert "shared across Xvond" in POLISH
    assert "affect every company" in POLISH
    assert "Create Global Package" in POLISH
    assert "Edit Global Package" in POLISH


def test_service_subscription_mutations_are_audited():
    assert "service_subscription.assigned" in API
    assert "service_subscription.renewed" in API
    assert "service_subscription.status_changed" in API
    assert '"previous_status": previous_status' in API
    assert '"previous_plan_id": previous_plan_id' in API
