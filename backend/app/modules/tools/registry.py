from backend.app.core.error_safety import safe_error_label
from backend.app.modules.tools.base import AgentTool, ToolResult


class ToolExecutionError(RuntimeError):
    """Safe tool-boundary exception.

    Tool implementations can call third-party SDKs whose exception strings may
    contain credentials, request bodies, or customer data. Only a structural
    label may escape into the runtime/audit path.
    """


class _SafeToolProxy(AgentTool):
    def __init__(self, tool: AgentTool):
        self._tool = tool
        self.name = tool.name
        self.description = tool.description
        self.input_schema = tool.input_schema

    def execute(self, arguments: dict, context: dict) -> ToolResult:
        try:
            return self._tool.execute(arguments=arguments, context=context)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(safe_error_label(exc)) from exc


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

        if isinstance(tool, _SafeToolProxy):
            self._tools[tool.name] = tool
        else:
            self._tools[tool.name] = _SafeToolProxy(tool)

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
