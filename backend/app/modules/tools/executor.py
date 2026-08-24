
from backend.app.core.config_secrets import reveal_config
from backend.app.core.module_access import require_company_module

from backend.app.modules.tools.models import (
    AgentToolAssignment,
)
from backend.app.modules.tools.registry import (
    tool_registry,
)
from backend.app.modules.tools.bootstrap import (
    register_builtin_tools,
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

    def execute(
        self,
        db,
        company_id: int,
        agent_id: int,
        tool_name: str,
        arguments: dict,
        conversation_id: int | None = None,
    ) -> dict:

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
                reveal_config(assignment.config),
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
