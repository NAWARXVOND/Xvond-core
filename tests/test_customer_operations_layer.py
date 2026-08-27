from backend.app.main import app
from backend.app.modules.customer_ops.models import CustomerRecord, NotificationEvent, NotificationPreference
from backend.app.api.admin_customer_operations import DEFAULT_EVENTS, _identity


def test_customer_operations_routes_are_mounted_once_under_admin():
    paths = set(app.openapi()["paths"])
    assert "/admin/customer-operations/companies/{company_id}/customers" in paths
    assert "/admin/customer-operations/companies/{company_id}/notifications" in paths
    assert "/admin/customer-operations/companies/{company_id}/analytics" in paths
    assert not any(path.startswith("/admin/admin/customer-operations") for path in paths)


def test_customer_identity_prefers_stable_contact_fields():
    assert _identity(phone="+968 99 123 456", email="a@example.com", external="abc") == "phone:+96899123456"
    assert _identity(email="A@Example.com") == "email:a@example.com"
    assert _identity(external=" Visitor-10 ") == "external:visitor-10"


def test_notification_defaults_cover_business_and_runtime_attention():
    assert set(DEFAULT_EVENTS) == {
        "booking_new",
        "order_new",
        "lead_new",
        "handoff_pending",
        "operation_attention",
        "ai_failure",
    }


def test_customer_operations_models_are_registered():
    assert CustomerRecord.__tablename__ == "customer_records"
    assert NotificationPreference.__tablename__ == "notification_preferences"
    assert NotificationEvent.__tablename__ == "notification_events"
