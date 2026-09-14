from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIUsage
from backend.app.modules.billing.service_models import ServiceSubscription
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.tools.business_models import ActionRequest

router = APIRouter(prefix="/admin/dashboard", tags=["Xvond Admin - Dashboard"])
UNRESOLVED_EXTERNAL = {"executing", "external_failed", "cancelling"}


@router.get("/summary")
def summary(current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        day_ago = now - timedelta(hours=24)
        month_ago = now - timedelta(days=30)

        companies = db.query(func.count(Company.id)).scalar() or 0
        active_companies = (
            db.query(func.count(Company.id))
            .filter(Company.active.is_(True))
            .scalar()
            or 0
        )
        agents = db.query(func.count(AIAgent.id)).scalar() or 0
        active_agents = (
            db.query(func.count(AIAgent.id))
            .filter(AIAgent.enabled.is_(True))
            .scalar()
            or 0
        )
        failed_ai_24h = (
            db.query(func.count(AIUsage.id))
            .filter(
                AIUsage.status == "failed",
                AIUsage.created_at >= day_ago,
            )
            .scalar()
            or 0
        )
        unresolved_external = (
            db.query(func.count(ActionRequest.id))
            .filter(ActionRequest.status.in_(UNRESOLVED_EXTERNAL))
            .scalar()
            or 0
        )
        active_channels = (
            db.query(func.count(AgentChannel.id))
            .filter(AgentChannel.enabled.is_(True))
            .scalar()
            or 0
        )
        ai_requests_24h = (
            db.query(func.count(AIUsage.id))
            .filter(AIUsage.created_at >= day_ago)
            .scalar()
            or 0
        )
        provider_cost_30d = (
            db.query(func.coalesce(func.sum(AIUsage.provider_cost), 0))
            .filter(AIUsage.created_at >= month_ago)
            .scalar()
            or 0
        )

        return {
            "companies": companies,
            "active_companies": active_companies,
            "inactive_companies": max(0, companies - active_companies),
            "users": db.query(func.count(User.id)).scalar() or 0,
            "agents": agents,
            "active_agents": active_agents,
            "inactive_agents": max(0, agents - active_agents),
            "active_channels": active_channels,
            "conversations": db.query(func.count(AIConversation.id)).scalar() or 0,
            "ai_requests": db.query(func.count(AIUsage.id)).scalar() or 0,
            "ai_requests_24h": ai_requests_24h,
            "failed_ai_requests_24h": failed_ai_24h,
            "unresolved_external_operations": unresolved_external,
            "total_tokens": db.query(
                func.coalesce(func.sum(AIUsage.total_tokens), 0)
            ).scalar() or 0,
            "provider_cost": db.query(
                func.coalesce(func.sum(AIUsage.provider_cost), 0)
            ).scalar() or 0,
            "provider_cost_30d": provider_cost_30d,
            "active_subscriptions": db.query(func.count(ServiceSubscription.id)).filter(
                ServiceSubscription.status == "active",
                ServiceSubscription.current_period_start <= now,
                ServiceSubscription.current_period_end > now,
            ).scalar() or 0,
            "attention": {
                "inactive_companies": max(0, companies - active_companies),
                "inactive_agents": max(0, agents - active_agents),
                "failed_ai_requests_24h": failed_ai_24h,
                "unresolved_external_operations": unresolved_external,
            },
        }
    finally:
        db.close()
