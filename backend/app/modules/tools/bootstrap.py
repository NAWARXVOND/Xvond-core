from backend.app.modules.tools.builtin import BUILTIN_TOOLS
from backend.app.modules.tools.registry import tool_registry
from backend.app.modules.tools.workflow_action_request import workflow_action_request_tool


# Human handoff is Xvond control-plane state, not an external business side effect.
# All customer business execution (booking, orders, webhooks, custom APIs, CRM/POS/
# ERP and future operations) must go through WorkflowActionRequestTool -> Workflow
# Engine. Legacy builtin implementations remain importable only for migration/tests;
# they are deliberately not registered into the live AI runtime.
_CONTROL_PLANE_BUILTINS = {"human_handoff"}


def register_builtin_tools():
    safe_builtins = [
        tool for tool in BUILTIN_TOOLS if tool.name in _CONTROL_PLANE_BUILTINS
    ]
    for tool in [*safe_builtins, workflow_action_request_tool]:
        if not tool_registry.exists(tool.name):
            tool_registry.register(tool)
    return [tool.name for tool in tool_registry.list()]
