from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.ai_agent.models import (
    AIAgent,
    AIConversation,
    AIUsage,
)

from backend.app.modules.billing.models import (
    Subscription,
)


router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Xvond Admin - Dashboard"],
)


@router.get("/summary")
def summary(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        companies = (
            db.query(func.count(Company.id))
            .scalar()
        )

        active_companies = (
            db.query(func.count(Company.id))
            .filter(
                Company.active.is_(True)
            )
            .scalar()
        )

        users = (
            db.query(func.count(User.id))
            .scalar()
        )

        agents = (
            db.query(func.count(AIAgent.id))
            .scalar()
        )

        active_agents = (
            db.query(func.count(AIAgent.id))
            .filter(
                AIAgent.enabled.is_(True)
            )
            .scalar()
        )

        conversations = (
            db.query(
                func.count(AIConversation.id)
            )
            .scalar()
        )

        ai_requests = (
            db.query(func.count(AIUsage.id))
            .scalar()
        )

        total_tokens = (
            db.query(
                func.coalesce(
                    func.sum(
                        AIUsage.total_tokens
                    ),
                    0,
                )
            )
            .scalar()
        )

        provider_cost = (
            db.query(
                func.coalesce(
                    func.sum(
                        AIUsage.provider_cost
                    ),
                    0,
                )
            )
            .scalar()
        )

        subscriptions = (
            db.query(
                func.count(Subscription.id)
            )
            .filter(
                Subscription.status
                == "active"
            )
            .scalar()
        )

        return {
            "companies": companies,
            "active_companies": active_companies,
            "users": users,
            "agents": agents,
            "active_agents": active_agents,
            "conversations": conversations,
            "ai_requests": ai_requests,
            "total_tokens": total_tokens,
            "provider_cost": provider_cost,
            "active_subscriptions": subscriptions,
        }

    finally:
        db.close()
