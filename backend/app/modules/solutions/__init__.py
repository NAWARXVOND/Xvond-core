from backend.app.core.module import BaseModule
from backend.app.modules.solutions.models import CompanySolution


class SolutionsModule(BaseModule):
    name = "solutions"
    version = "1.0.0"
    description = "Xvond company service portfolio and provisioning"
