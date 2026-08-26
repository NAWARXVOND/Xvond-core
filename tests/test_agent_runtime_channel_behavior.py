from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.app.core.agent_runtime import AgentRuntime


def test_runtime_resolves_whatsapp_channel_behavior():
    db = MagicMock()

    whatsapp_session = SimpleNamespace(
        company_id=7,
        agent_id=11,
        conversation_id=22,
    )
    channel = SimpleNamespace(
        company_id=7,
        agent_id=11,
        channel_type="whatsapp",
        enabled=True,
        config={
            "language": "ar",
            "dialect": "omani",
            "tone": "friendly",
            "response_length": "short",
            "emoji_style": "minimal",
        },
    )

    session_query = MagicMock()
    session_query.filter.return_value.first.return_value = whatsapp_session

    channel_query = MagicMock()
    channel_query.filter.return_value.first.return_value = channel

    db.query.side_effect = [session_query, channel_query]

    channel_type, behavior = AgentRuntime().resolve_channel_behavior(
        db=db,
        company_id=7,
        agent_id=11,
        conversation_id=22,
    )

    assert channel_type == "whatsapp"
    assert "RESPONSE LANGUAGE: ar" in behavior
    assert "DIALECT: omani" in behavior
    assert "TONE: friendly" in behavior
    assert "RESPONSE LENGTH: short" in behavior


def test_runtime_has_no_channel_behavior_without_channel_session():
    db = MagicMock()
    session_query = MagicMock()
    session_query.filter.return_value.first.return_value = None
    db.query.return_value = session_query

    channel_type, behavior = AgentRuntime().resolve_channel_behavior(
        db=db,
        company_id=7,
        agent_id=11,
        conversation_id=22,
    )

    assert channel_type is None
    assert behavior == ""
