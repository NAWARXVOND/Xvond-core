from backend.app.modules.tools.executor import tool_requires_approval
from backend.app.modules.tools.models import ToolApprovalRequest


def test_sensitive_tools_require_approval_by_default():
    for name in ("booking", "order", "webhook", "custom_api"):
        assert tool_requires_approval(name, {}) is True


def test_safe_tools_execute_without_approval_by_default():
    for name in ("lead", "human_handoff", "echo"):
        assert tool_requires_approval(name, {}) is False


def test_assignment_can_require_more_approval_but_cannot_bypass_sensitive_policy():
    assert tool_requires_approval("lead", {"approval_required": True}) is True
    assert tool_requires_approval("booking", {"approval_required": False}) is True


def test_tool_approval_request_carries_execution_context():
    item = ToolApprovalRequest(
        company_id=1,
        agent_id=2,
        conversation_id=3,
        tool_name="order",
        arguments={"items": [{"sku": "A"}]},
        status="pending",
    )

    assert item.company_id == 1
    assert item.agent_id == 2
    assert item.tool_name == "order"
    assert item.status == "pending"
