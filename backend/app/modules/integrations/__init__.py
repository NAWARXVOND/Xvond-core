from backend.app.core.module import BaseModule
from backend.app.modules.integrations.models import CompanyIntegration


class IntegrationsModule(BaseModule):
    name = "integrations"
    version = "1.0.0"
    description = "Xvond External Integrations"
