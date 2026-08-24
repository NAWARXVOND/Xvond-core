from types import SimpleNamespace

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
)
from backend.app.modules.tools.executor import (
    tool_executor,
)
from backend.app.modules.tools.models import (
    AgentToolAssignment,
)


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.result


class ScopeDatabase:
    def __init__(self, agent=None, conversation=None):
        self.agent = agent
        self.conversation = conversation
        self.queried = []

    def query(self, model):
        self.queried.append(model)

        if model is AIAgent:
            return FakeQuery(self.agent)

        if model is AIConversation:
            return FakeQuery(self.conversation)

        raise AssertionError(
            f"Unexpected query outside tenant scope: {model}"
        )


def test_cross_company_agent_is_rejected_before_tool_lookup():
    db = ScopeDatabase(agent=None)

    result = tool_executor.execute(
        db=db,
        company_id=1,
        agent_id=200,
        tool_name="echo",
        arguments={"message": "should not run"},
    )

    assert result["success"] is False
    assert result["error"] == (
        "Agent does not belong to this company"
    )
    assert AgentToolAssignment not in db.queried


def test_cross_company_conversation_is_rejected_before_tool_lookup():
    db = ScopeDatabase(
        agent=SimpleNamespace(id=10, company_id=1),
        conversation=None,
    )

    result = tool_executor.execute(
        db=db,
        company_id=1,
        agent_id=10,
        conversation_id=999,
        tool_name="echo",
        arguments={"message": "should not run"},
    )

    assert result["success"] is False
    assert result["error"] == (
        "Conversation does not belong to "
        "this company and agent"
    )
    assert AgentToolAssignment not in db.queried


def test_valid_scope_does_not_return_scope_error():
    db = ScopeDatabase(
        agent=SimpleNamespace(id=10, company_id=1),
        conversation=SimpleNamespace(
            id=20,
            company_id=1,
            agent_id=10,
        ),
    )

    assert tool_executor.validate_execution_scope(
        db=db,
        company_id=1,
        agent_id=10,
        conversation_id=20,
    ) is None
