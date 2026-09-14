from pathlib import Path

from backend.app.core.admin_privacy import sanitize_admin_audit_details
from backend.app.modules.customer_ops.service import identity_key, normalize_phone


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
CUSTOMER_API = (
    ROOT / "backend" / "app" / "api" / "customer_operations.py"
).read_text(encoding="utf-8")
CUSTOMER_SERVICE = (
    ROOT / "backend" / "app" / "modules" / "customer_ops" / "service.py"
).read_text(encoding="utf-8")
MEMORY = (
    ROOT / "backend" / "app" / "modules" / "customer_ops" / "memory.py"
).read_text(encoding="utf-8")
ADMIN_INDEX = (ROOT / "frontend" / "admin" / "index.html").read_text(encoding="utf-8")
CUSTOMER_INDEX = (ROOT / "frontend" / "customer" / "index.html").read_text(encoding="utf-8")


def test_customer_operations_are_tenant_scoped_and_not_admin_mounted():
    assert "admin_customer_operations_router" not in MAIN
    assert "customer_operations_router" in MAIN
    assert 'prefix="/customer/operations"' in CUSTOMER_API
    assert CUSTOMER_API.count("Depends(require_customer_manager)") >= 7
    assert '@router.get("/customers")' in CUSTOMER_API
    assert '@router.get("/customers/{customer_id}")' in CUSTOMER_API
    assert '@router.put("/customers/{customer_id}")' in CUSTOMER_API
    assert "{company_id}" not in CUSTOMER_API


def test_customer_operations_ui_is_customer_only():
    assert "/static/admin/customer-operations.js" not in ADMIN_INDEX
    assert "/static/customer/customer-operations.js" in CUSTOMER_INDEX
    assert not (ROOT / "frontend" / "admin" / "customer-operations.js").exists()
    assert not (ROOT / "backend" / "app" / "api" / "admin_customer_operations.py").exists()


def test_notification_delivery_does_not_claim_unimplemented_destinations():
    assert 'SUPPORTED_NOTIFICATION_DESTINATIONS = {"dashboard"}' in CUSTOMER_SERVICE
    assert "row.email = None" in CUSTOMER_SERVICE
    assert "row.whatsapp = None" in CUSTOMER_SERVICE
    assert "row.webhook_url = None" in CUSTOMER_SERVICE


def test_whatsapp_identity_uses_phone_as_canonical_customer_key():
    assert normalize_phone("+968 99-123-456") == "+96899123456"
    assert identity_key(
        external="+968 99-123-456",
        channel="whatsapp",
    ) == "phone:+96899123456"
    assert "canonical_key = identity_key(" in MEMORY
    assert "CustomerRecord.identity_key == canonical_key" in MEMORY


def test_admin_audit_details_are_recursively_redacted():
    sanitized = sanitize_admin_audit_details(
        {
            "status": "assigned",
            "external_contact_id": "+96899999999",
            "nested": {
                "phone_number": "+96811111111",
                "safe_status": "ok",
            },
            "items": [
                {"customer_name": "Private Name", "result": "success"},
            ],
        }
    )
    assert sanitized["status"] == "assigned"
    assert sanitized["external_contact_id"] == "[redacted]"
    assert sanitized["nested"]["phone_number"] == "[redacted]"
    assert sanitized["nested"]["safe_status"] == "ok"
    assert sanitized["items"][0]["customer_name"] == "[redacted]"
    assert sanitized["items"][0]["result"] == "success"
