import inspect

from backend.app.core.agent_runtime import AgentRuntime
from backend.app.api import whatsapp_webhook


def test_agent_runtime_can_defer_commit_for_delivery_transaction():
    signature = inspect.signature(AgentRuntime.chat)
    assert "commit" in signature.parameters
    assert signature.parameters["commit"].default is True


def test_whatsapp_runtime_defers_commit_until_delivery():
    source = inspect.getsource(whatsapp_webhook.process_webhook_payload)
    assert "commit=False" in source
    assert "db.rollback()" in source
    assert "WhatsApp reply delivery failed" in source
