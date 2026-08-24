from backend.app.core.module import BaseModule

from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
    CompanyAIProfile,
)


class ProvidersModule(BaseModule):
    name = "providers"
    version = "1.0.0"
    description = "Xvond AI Provider and Model Catalog"
