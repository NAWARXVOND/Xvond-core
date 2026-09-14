import inspect

from backend.app.api import admin_operations


def test_unresolved_delivery_metadata_excludes_customer_payload():
    source = inspect.getsource(admin_operations._delivery_metadata)
    assert '"conversation_id"' in source
    assert '"status"' in source
    assert '"attempts"' in source
    assert '"last_error_code"' in source
    assert '"content"' not in source
    assert '"wa_id"' not in source
    assert '"inbound_external_message_id"' not in source


def test_unknown_delivery_cannot_be_blindly_retried():
    source = inspect.getsource(admin_operations.retry_whatsapp_delivery)
    assert 'if row.status == "unknown"' in source
    assert "must be reconciled before any resend" in source
    assert 'row.status != "failed" or not row.retryable' in source
    assert "attempt_delivery(" in source


def test_manual_delivery_retry_is_admin_only_and_audited():
    signature = inspect.signature(admin_operations.retry_whatsapp_delivery)
    assert "current_admin" in signature.parameters
    source = inspect.getsource(admin_operations.retry_whatsapp_delivery)
    assert "require_xvond_admin" in str(signature)
    assert 'action="whatsapp.delivery_retry_requested"' in source
    assert 'action="whatsapp.delivery_retry_completed"' in source
    assert 'resource_type="whatsapp_delivery"' in source


def test_unresolved_delivery_listing_is_bounded():
    source = inspect.getsource(admin_operations.unresolved_whatsapp_deliveries)
    assert "min(int(limit or 100), 500)" in source
    assert "WhatsAppOutboundDelivery.status.in_(UNRESOLVED_DELIVERY)" in source
