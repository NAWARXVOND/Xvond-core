from backend.app.core.module import BaseModule
from backend.app.modules.analytics.models import AnalyticsSource, AnalyticsDashboard


class AnalyticsModule(BaseModule):
    name = "analytics"
    version = "1.0.0"
    description = "Xvond business data and AI analytics"
