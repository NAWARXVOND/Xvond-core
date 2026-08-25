from backend.app.core.module import BaseModule
from backend.app.modules.automation.models import AutomationWorkflow, AutomationRun


class AutomationModule(BaseModule):
    name = "automation"
    version = "1.0.0"
    description = "Xvond business automation workflows"
