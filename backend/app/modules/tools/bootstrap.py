from backend.app.modules.tools.builtin import BUILTIN_TOOLS
from backend.app.modules.tools.registry import tool_registry


def register_builtin_tools():
    for tool in BUILTIN_TOOLS:
        if not tool_registry.exists(tool.name):
            tool_registry.register(tool)

    return [
        tool.name
        for tool in tool_registry.list()
    ]
