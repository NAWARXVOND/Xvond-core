import inspect

from backend.app.core.agent_runtime import AgentRuntime
from backend.app.api import whatsapp_webhook
from backend.app.modules.channels import whatsapp_delivery


def test_agent_runtime_can_defer_commit_for_delivery_transaction():
    signature = inspect.signature(AgentRuntime.chat)
    assert "commit" in signature.parameters
    assert signature.parameters["commit"].default is True


def test_whatsapp_runtime_persists_turn_before_transport_attempt():
    source = inspect.getsource(whatsapp_webhook.process_webhook_payload)
    assert "commit=False" in source
    assert "ensure_delivery(" in source
    assert "complete_message_claim(" in source
    delivery_position = source.index("ensure_delivery(")
    commit_position = source.index("db.commit()", delivery_position)
    attempt_position = source.index("attempt_delivery(", commit_position)
    assert delivery_position < commit_position < attempt_position


def test_delivery_worker_does_not_blindly_resend_ambiguous_sends():
    source = inspect.getsource(whatsapp_delivery.attempt_delivery)
    assert 'if row.status == "sending"' in source
    assert 'row.status = "unknown"' in source
    assert '"interrupted_after_send_started"' in source
    assert "provider_message_id_conflict" in source
