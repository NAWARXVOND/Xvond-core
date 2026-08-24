from backend.app.core.module import BaseModule
from backend.app.modules.billing.models import (
    Invoice,
    Plan,
    Subscription,
)


class BillingModule(BaseModule):
    name = "billing"
    version = "1.0.0"
    description = "Xvond Plans, Subscriptions and Billing"
