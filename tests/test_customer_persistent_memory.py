import inspect

from backend.app.core.agent_runtime import AgentRuntime, GROUNDING_POLICY
from backend.app.modules.customer_ops import memory


def test_customer_memory_is_injected_into_runtime():
    source = inspect.getsource(AgentRuntime.chat)
    assert "build_customer_memory(db, conversation)" in source
    assert "CUSTOMER MEMORY (persistent continuity; use only when relevant)" in source


def test_customer_memory_is_bounded():
    assert memory.CUSTOMER_MEMORY_MAX_MESSAGES == 32
    assert memory.CUSTOMER_MEMORY_MAX_CHARS == 6000
    source = inspect.getsource(memory._older_customer_messages)
    assert ".offset(32)" in source
    assert ".limit(CUSTOMER_MEMORY_MAX_MESSAGES)" in source


def test_customer_memory_tracks_whatsapp_identity():
    source = inspect.getsource(memory.get_or_touch_customer)
    assert "conversation.external_contact_id" in source
    assert '== "whatsapp"' in source
    assert "row.last_seen_at = now" in source


def test_short_messages_do_not_restart_existing_conversation():
    assert "Never restart the conversation" in GROUNDING_POLICY
    assert "emoji" in GROUNDING_POLICY
