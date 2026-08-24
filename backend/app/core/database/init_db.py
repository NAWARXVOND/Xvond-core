from backend.app.core.database.base import Base
from backend.app.core.database.connection import engine

import backend.app.models
import backend.app.models.password_reset

import backend.app.modules.ai_agent.models
import backend.app.modules.ai_agent.factory_models

import backend.app.modules.knowledge.models
import backend.app.modules.tools.models
import backend.app.modules.channels.models
import backend.app.modules.integrations.models
import backend.app.modules.billing.models
import backend.app.modules.audit.models
import backend.app.modules.providers.models


def init_db():
    Base.metadata.create_all(
        bind=engine
    )
