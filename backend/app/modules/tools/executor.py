
from backend.app.core.config_secrets import reveal_config
from backend.app.core.module_access import require_company_module

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
)
from backend.app.modules.tools.models import (
    AgentToolAssignment,
    ToolApprovalRequest,
)
from backend.app.modules.tools.registry import (
    tool_registry,
)
from backend.app.modules.tools.bootstrap import (
    register_builtin_tools,
)


SENSITIVE_TOOLS = {
    "booking",
    "order",
    "webhook",
    "custom_api",
}


def tool_requires_approval(tool_name: str, config: dict | None) -> bool:
    config = config or {}
    return bool(
        tool_name in SENSITIVE_TOOLS
        or config.get("approval_required", False)
    )


class ToolExecutor:

    def __init__(self):
        register_builtin_tools()

    def get_agent_tools(
        self,
        db,
        agent_id: int,
    ) -> list[dict]:

        assignments = (
            db.query(AgentToolAssignment)
            .filter(
                AgentToolAssignment.agent_id
                == agent_id,
                AgentToolAssignment.enabled
                .is_(True),
            )
            .order_by(
                AgentToolAssignment.id.asc()
            )
            .all()
        )

        result = []

        for assignment in assignments:

            tool = tool_registry.get(
                assignment.tool_name
            )

            if tool is None:
                continue

            result.append({
                "name":
                    tool.name,
                "description":
                    tool.description,
                "input_schema":
                    tool.input_schema,
                # Configuration is intentionally
                # not exposed to the AI model/API.
            })

        return result

    def validate_execution_scope(
        self,
        db,
        company_id: int,
        agent_id: int,
        conversation_id: int | None = None,
    ) -> str | None:
        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            )
            .first()
        )

        if agent is None:
            return "Agent does not belong to this company"

        if conversation_id is None:
            return None

        conversation = (
            db.query(AIConversation)
            .filter(
                AIConversation.id == conversation_id,
                AIConversation.company_id == company_id,
                AIConversation.agent_id == agent_id,
            )
            .first()
        )

        if conversation is None:
            return (
                "Conversation does not belong to "
                "this company and agent"
            )

        return None

    def execute(
        self,
        db,
        company_id: int,
        agent_id: int,
        tool_name: str,
        arguments: dict,
        conversation_id: int | None = None,
        approval_granted: bool = False,
    ) -> dict:

        scope_error = self.validate_execution_scope(
            db=db,
            company_id=company_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
        )

        if scope_error is not None:
            return {
                "success": False,
                "tool": tool_name,
                "data": None,
                "error": scope_error,
            }

        require_company_module(
            db,
            company_id,
            "tools",
        )

        assignment = (
            db.query(AgentToolAssignment)
            .filter(
                AgentToolAssignment.agent_id
                == agent_id,
                AgentToolAssignment.tool_name
                == tool_name,
                AgentToolAssignment.enabled
                .is_(True),
            )
            .first()
        )

        if assignment is None:
            return {
                "success": False,
                "tool": tool_name,
                "data": None,
                "error":
                    "Tool is not assigned to this agent",
            }

        tool = tool_registry.get(
            tool_name
        )

        if tool is None:
            return {
                "success": False,
                "tool": tool_name,
                "data": None,
                "error":
                    "Tool is not registered",
            }

        config = reveal_config(assignment.config)
        approval_required = tool_requires_approval(
            tool_name,
            config,
        )

        if approval_required and not approval_granted:
            request = ToolApprovalRequest(
                company_id=company_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                tool_name=tool_name,
                arguments=arguments or {},
                status="pending",
            )
            db.add(request)
            db.flush()

            return {
                "success": False,
                "tool": tool_name,
                "data": {
                    "approval_request_id": request.id,
                    "status": "pending_approval",
                },
                "error": "Tool execution requires human approval",
                "approval_required": True,
            }

        context = {
            "db":
                db,
            "company_id":
                company_id,
            "agent_id":
                agent_id,
            "conversation_id":
                conversation_id,
            "config":
                config,
        }

        try:

            # SAVEPOINT:
            # failed tool database operations
            # roll back only this tool.
            with db.begin_nested():

                result = tool.execute(
                    arguments=arguments or {},
                    context=context,
                )

                # Force SQL errors to happen
                # inside this savepoint.
                db.flush()

            return {
                "success":
                    bool(result.success),
                "tool":
                    tool_name,
                "data":
                    result.data,
                "error":
                    result.error,
            }

        except Exception as exc:

            return {
                "success": False,
                "tool": tool_name,
                "data": None,
                "error": str(exc),
            }


tool_executor = ToolExecutor()
