from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIUsage
from backend.app.modules.billing.service_models import ServiceSubscription

router = APIRouter(prefix="/admin/dashboard", tags=["Xvond Admin - Dashboard"])


@router.get("/summary")
def summary(current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        return {
            "companies": db.query(func.count(Company.id)).scalar() or 0,
            "active_companies": db.query(func.count(Company.id)).filter(
                Company.active.is_(True)
            ).scalar() or 0,
            "users": db.query(func.count(User.id)).scalar() or 0,
            "agents": db.query(func.count(AIAgent.id)).scalar() or 0,
            "active_agents": db.query(func.count(AIAgent.id)).filter(
                AIAgent.enabled.is_(True)
            ).scalar() or 0,
            "conversations": db.query(func.count(AIConversation.id)).scalar() or 0,
            "ai_requests": db.query(func.count(AIUsage.id)).scalar() or 0,
            "total_tokens": db.query(
                func.coalesce(func.sum(AIUsage.total_tokens), 0)
            ).scalar() or 0,
            "provider_cost": db.query(
                func.coalesce(func.sum(AIUsage.provider_cost), 0)
            ).scalar() or 0,
            "active_subscriptions": db.query(func.count(ServiceSubscription.id)).filter(
                ServiceSubscription.status == "active",
                ServiceSubscription.current_period_start <= now,
                ServiceSubscription.current_period_end > now,
            ).scalar() or 0,
        }
    finally:
        db.close()
