from backend.app.modules.tools.base import AgentTool


class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, AgentTool] = {}

    def register(
        self,
        tool: AgentTool,
    ):
        if not tool.name:
            raise ValueError(
                "Tool must have a name"
            )

        self._tools[tool.name] = tool

    def get(
        self,
        name: str,
    ) -> AgentTool | None:
        return self._tools.get(name)

    def exists(
        self,
        name: str,
    ) -> bool:
        return name in self._tools

    def list(
        self,
    ) -> list[AgentTool]:
        return list(
            self._tools.values()
        )


tool_registry = ToolRegistry()
