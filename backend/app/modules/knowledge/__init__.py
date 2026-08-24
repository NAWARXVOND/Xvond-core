from backend.app.core.module import BaseModule

from backend.app.modules.knowledge.models import (
    AgentKnowledge,
    KnowledgeDocument,
)


class KnowledgeModule(BaseModule):
    name = "knowledge"
    version = "1.0.0"
    description = "Xvond Company Knowledge Base"
