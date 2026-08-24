
from backend.app.modules.audit.models import (
    AuditLog,
)


class AuditService:

    def log(
        self,
        db,
        action: str,
        resource_type: str,
        resource_id=None,
        user_id: int | None = None,
        company_id: int | None = None,
        details: dict | None = None,
    ):

        item = AuditLog(
            user_id=user_id,
            company_id=company_id,
            action=action,
            resource_type=resource_type,
            resource_id=(
                str(resource_id)
                if resource_id is not None
                else None
            ),
            details=details or {},
        )

        db.add(item)

        return item


audit_service = AuditService()
