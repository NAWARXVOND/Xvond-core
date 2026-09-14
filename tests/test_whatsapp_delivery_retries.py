import inspect
from pathlib import Path

from backend.app.api import whatsapp_webhook
from backend.app.modules.channels import whatsapp_delivery

SOURCE = Path("backend/app/api/whatsapp_webhook.py").read_text(encoding="utf-8")


def test_unknown_phone_numbers_are_not_queued():
    assert "matched_channels == 0" in SOURCE
    assert '"unknown_phone_number_id"' in SOURCE


def test_retry_uses_durable_delivery_instead_of_replaying_ai_turn():
    webhook_source = inspect.getsource(whatsapp_webhook.process_webhook_payload)
    retry_source = inspect.getsource(whatsapp_delivery.retry_delivery_for_inbound)
    assert "retry_delivery_for_inbound(" in webhook_source
    assert "delivery_for_inbound(" in retry_source
    assert "attempt_delivery(" in retry_source
    assert 'row.status == "unknown"' in retry_source
    assert 'row.status == "failed" and not row.retryable' in retry_source


def test_retryable_rejection_preserves_business_turn_and_retries_transport_only():
    source = inspect.getsource(whatsapp_delivery.attempt_delivery)
    assert 'certainty == "rejected"' in source
    assert 'row.status = "failed"' in source
    assert 'row.retryable = bool(result.get("retryable"))' in source
    assert "whatsapp_sender.send_text(" in source
    assert "agent_runtime" not in source


def test_ambiguous_network_outcome_requires_reconciliation_not_blind_retry():
    source = inspect.getsource(whatsapp_delivery.attempt_delivery)
    assert 'row.status = "unknown"' in source
    assert 'row.retryable = False' in source
    assert '"network_outcome_unknown"' in source
    assert '"interrupted_after_send_started"' in source
