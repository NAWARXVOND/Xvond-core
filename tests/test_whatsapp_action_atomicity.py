import inspect

from backend.app.core.agent_runtime import AgentRuntime
from backend.app.core.ai.providers.groq import GroqProvider
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


def test_groq_provider_does_not_use_unsupported_previous_response_id():
    source = inspect.getsource(GroqProvider.generate)
    assert "previous_response_id" not in source
    assert "tool_call_id" in source
    assert "chat/completions" in GroqProvider._request_url.__code__.co_consts
