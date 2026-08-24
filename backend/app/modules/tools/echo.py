from backend.app.modules.tools.base import (
    AgentTool,
    ToolResult,
)


class EchoTool(AgentTool):
    name = "echo"
    description = "Development test tool"

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

        return ToolResult(
            success=True,
            data={
                "arguments": arguments,
                "context": context,
            },
        )
