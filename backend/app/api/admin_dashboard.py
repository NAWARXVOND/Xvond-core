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
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(prefix="/admin/dashboard", tags=["Xvond Admin - Dashboard"])


@router.get("/summary")
def summary(current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        since_24h = now - timedelta(hours=24)
        expires_before = now + timedelta(days=7)

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
        channels = db.query(func.count(AgentChannel.id)).scalar() or 0
        active_channels = (
            db.query(func.count(AgentChannel.id))
            .filter(AgentChannel.enabled.is_(True))
            .scalar()
            or 0
        )

        active_agent_exists = db.query(AIAgent.id).filter(
            AIAgent.company_id == Company.id,
            AIAgent.enabled.is_(True),
        ).exists()
        active_companies_without_active_employee = (
            db.query(func.count(Company.id))
            .filter(
                Company.active.is_(True),
                ~active_agent_exists,
            )
            .scalar()
            or 0
        )

        active_channel_exists = db.query(AgentChannel.id).filter(
            AgentChannel.agent_id == AIAgent.id,
            AgentChannel.company_id == AIAgent.company_id,
            AgentChannel.enabled.is_(True),
        ).exists()
        active_employees_without_active_channel = (
            db.query(func.count(AIAgent.id))
            .join(Company, Company.id == AIAgent.company_id)
            .filter(
                Company.active.is_(True),
                AIAgent.enabled.is_(True),
                ~active_channel_exists,
            )
            .scalar()
            or 0
        )

        usage_24h = (
            db.query(
                func.count(AIUsage.id),
                func.coalesce(func.sum(AIUsage.total_tokens), 0),
                func.coalesce(func.sum(AIUsage.provider_cost), 0),
                func.coalesce(func.avg(AIUsage.latency_ms), 0),
            )
            .filter(AIUsage.created_at >= since_24h)
            .one()
        )
        failed_ai_requests_24h = (
            db.query(func.count(AIUsage.id))
            .filter(
                AIUsage.created_at >= since_24h,
                AIUsage.status != "success",
            )
            .scalar()
            or 0
        )
        active_handoffs = (
            db.query(func.count(HumanHandoff.id))
            .filter(HumanHandoff.status.in_(["pending", "in_progress"]))
            .scalar()
            or 0
        )
        expiring_subscriptions_7d = (
            db.query(func.count(ServiceSubscription.id))
            .filter(
                ServiceSubscription.status == "active",
                ServiceSubscription.current_period_start <= now,
                ServiceSubscription.current_period_end > now,
                ServiceSubscription.current_period_end <= expires_before,
            )
            .scalar()
            or 0
        )

        return {
            "generated_at": now.isoformat(),
            "companies": companies,
            "active_companies": active_companies,
            "inactive_companies": max(0, companies - active_companies),
            "users": db.query(func.count(User.id)).scalar() or 0,
            "agents": agents,
            "active_agents": active_agents,
            "draft_agents": max(0, agents - active_agents),
            "channels": channels,
            "active_channels": active_channels,
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
            "last_24h": {
                "ai_requests": usage_24h[0] or 0,
                "failed_ai_requests": failed_ai_requests_24h,
                "total_tokens": usage_24h[1] or 0,
                "provider_cost": usage_24h[2] or 0,
                "avg_latency_ms": round(float(usage_24h[3] or 0), 1),
            },
            "attention": {
                "active_companies_without_active_employee": active_companies_without_active_employee,
                "active_employees_without_active_channel": active_employees_without_active_channel,
                "failed_ai_requests_24h": failed_ai_requests_24h,
                "active_handoffs": active_handoffs,
                "subscriptions_expiring_7d": expiring_subscriptions_7d,
            },
        }
    finally:
        db.close()
