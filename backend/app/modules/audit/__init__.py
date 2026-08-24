from backend.app.core.module import BaseModule

from backend.app.modules.audit.models import AuditLog


class AuditModule(BaseModule):
    name = "audit"
    version = "1.0.0"
    description = "Xvond Audit Logging"
