
from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.dependencies import (
    require_xvond_admin,
)

from backend.app.models.user import User
from backend.app.modules.audit.models import (
    AuditLog,
)


router = APIRouter(
    prefix="/admin/audit",
    tags=["Xvond Admin - Audit"],
)


@router.get("/")
def list_audit_logs(
    company_id: int | None = Query(
        default=None
    ),
    action: str | None = Query(
        default=None
    ),
    resource_type: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=200,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        query = db.query(
            AuditLog
        )

        if company_id is not None:
            query = query.filter(
                AuditLog.company_id
                == company_id
            )

        if action:
            query = query.filter(
                AuditLog.action
                == action.strip()
            )

        if resource_type:
            query = query.filter(
                AuditLog.resource_type
                == resource_type.strip()
            )

        total = query.count()

        items = (
            query
            .order_by(
                AuditLog.id.desc()
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": [
                {
                    "id":
                        item.id,
                    "user_id":
                        item.user_id,
                    "company_id":
                        item.company_id,
                    "action":
                        item.action,
                    "resource_type":
                        item.resource_type,
                    "resource_id":
                        item.resource_id,
                    "details":
                        item.details,
                    "created_at":
                        item.created_at,
                }
                for item in items
            ],
        }

    finally:
        db.close()
