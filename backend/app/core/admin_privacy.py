from fastapi import APIRouter


# Xvond Admin is the platform/operator control plane. Customer conversation
# content and customer-created business requests belong to the tenant portal
# (or the tenant's connected external system), not the Xvond operator UI.
ADMIN_CUSTOMER_DATA_ROUTES = {
    "/admin/agent-actions/companies/{company_id}/requests",
    "/admin/agent-actions/requests/{request_id}",
}

_ADMIN_AUDIT_SENSITIVE_KEYS = {
    "address",
    "content",
    "conversation_id",
    "customer_id",
    "customer_name",
    "email",
    "external_contact_id",
    "message",
    "notes",
    "phone",
    "prompt",
    "text",
    "wa_id",
}
_ADMIN_AUDIT_SENSITIVE_CONTAINERS = {
    "customer",
    "customer_payload",
    "message_payload",
}
_REDACTED = "[redacted]"


def _admin_audit_key_is_sensitive(key: object) -> bool:
    normalized = str(key or "").strip().lower()
    if normalized in _ADMIN_AUDIT_SENSITIVE_KEYS:
        return True
    return any(
        token in normalized
        for token in (
            "customer_name",
            "external_contact",
            "phone_number",
            "whatsapp_number",
        )
    )


def sanitize_admin_audit_details(value):
    """Return operational audit metadata without tenant customer content.

    Audit records are shared infrastructure metadata, but their free-form
    details can be written by tenant workflows. Xvond Admin must never rely on
    every producer remembering the operator/customer privacy boundary.
    """
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key or "").strip().lower()
            if _admin_audit_key_is_sensitive(key) or normalized in _ADMIN_AUDIT_SENSITIVE_CONTAINERS:
                result[key] = _REDACTED
            else:
                result[key] = sanitize_admin_audit_details(item)
        return result
    if isinstance(value, list):
        return [sanitize_admin_audit_details(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_admin_audit_details(item) for item in value]
    return value


def enforce_admin_customer_data_boundary(router: APIRouter) -> None:
    """Remove customer-data management routes from an admin configuration router.

    The underlying customer APIs remain tenant-scoped. This keeps Xvond Admin
    focused on configuration and platform health while preventing accidental
    operator access to customer request payloads.
    """
    router.routes[:] = [
        route
        for route in router.routes
        if getattr(route, "path", None) not in ADMIN_CUSTOMER_DATA_ROUTES
    ]
