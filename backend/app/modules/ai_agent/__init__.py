from backend.app.core.module import BaseModule

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
    AIMessage,
    AIUsage,
)


class AIAgentModule(BaseModule):
    name = "ai_agent"
    version = "1.0.0"
    description = "Xvond AI Agent Runtime Module"
