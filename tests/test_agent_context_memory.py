import inspect

from backend.app.core.agent_runtime import AgentRuntime


def test_agent_history_is_bounded_and_recent_first():
    source = inspect.getsource(AgentRuntime.build_history)

    assert AgentRuntime.HISTORY_MAX_MESSAGES == 32
    assert AgentRuntime.HISTORY_MAX_CHARS == 8000
    assert ".limit(self.HISTORY_MAX_MESSAGES)" in source
    assert "order_by(AIMessage.id.desc())" in source
    assert "used_chars" in source
    assert "selected.reverse()" in source
    assert "[-12000:]" not in source


def test_agent_history_only_accepts_conversation_roles():
    assert AgentRuntime.HISTORY_ALLOWED_ROLES == {"user", "assistant", "human"}
