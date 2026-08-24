from backend.app.core.module import BaseModule

from backend.app.modules.tools.echo import EchoTool
from backend.app.modules.tools.models import AgentToolAssignment
from backend.app.modules.tools.registry import tool_registry


tool_registry.register(
    EchoTool()
)


class ToolsModule(BaseModule):
    name = "tools"
    version = "1.0.0"
    description = "Xvond Agent Tools System"
