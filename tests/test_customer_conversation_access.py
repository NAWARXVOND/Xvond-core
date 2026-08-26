from types import SimpleNamespace

from backend.app.modules.ai_agent.customer_access import can_view_conversations


def test_profile_employee_without_agent_config_can_view_conversations():
    assert can_view_conversations(None) is True


def test_explicit_customer_conversation_access_is_respected():
    assert can_view_conversations(
        SimpleNamespace(customer_controls={"can_view_conversations": True})
    ) is True
    assert can_view_conversations(
        SimpleNamespace(customer_controls={"can_view_conversations": False})
    ) is False


def test_existing_empty_agent_config_remains_restricted():
    assert can_view_conversations(SimpleNamespace(customer_controls={})) is False
