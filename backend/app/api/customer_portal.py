from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.app.core.config_secrets import configured_secret_fields, public_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_user
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIUsage
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.knowledge.models import KnowledgeDocument
from backend.app.modules.solutions.catalog import SERVICE_CATALOG

router = APIRouter(prefix="/customer", tags=["Customer Portal"])


def _service_data(db, subscription: ServiceSubscription, plan: ServicePlan) -> dict:
    usage = {}
    for metric, limit in (plan.limits or {}).items():
        usage[metric] = {
            "used": service_limits.used(db, subscription, metric),
            "limit": limit,
        }
    now = datetime.utcnow()
    effective_status = subscription.status
    if effective_status == "active" and not (
        subscription.current_period_start <= now < subscription.current_period_end
    ):
        effective_status = "expired"
    return {
        "id": subscription.id,
        "service_code": subscription.service_code,
        "service_name": SERVICE_CATALOG.get(subscription.service_code, {}).get(
            "name", subscription.service_code
        ),
        "status": effective_status,
        "current_period_start": subscription.current_period_start,
        "current_period_end": subscription.current_period_end,
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "tier": plan.tier,
            "monthly_price": plan.monthly_price,
            "currency": plan.currency,
            "limits": plan.limits or {},
        },
        "usage": usage,
    }


@router.get("/overview")
def overview(current_user: User = Depends(require_customer_user)):
    db = SessionLocal()
    try:
        company_id = current_user.company_id
        company = db.query(Company).filter(Company.id == company_id).first()

        service_rows = (
            db.query(ServiceSubscription, ServicePlan)
            .join(ServicePlan, ServicePlan.id == ServiceSubscription.plan_id)
            .filter(ServiceSubscription.company_id == company_id)
            .order_by(ServiceSubscription.service_code.asc())
            .all()
        )
        services = [_service_data(db, subscription, plan) for subscription, plan in service_rows]
        ai_service = next((x for x in services if x["service_code"] == "ai_agents"), None)

        agents = db.query(AIAgent).filter(AIAgent.company_id == company_id).all()
        channels = db.query(AgentChannel).filter(AgentChannel.company_id == company_id).all()
        integrations = db.query(CompanyIntegration).filter(
            CompanyIntegration.company_id == company_id
        ).all()
        usage = db.query(
            func.count(AIUsage.id),
            func.coalesce(func.sum(AIUsage.total_tokens), 0),
        ).filter(AIUsage.company_id == company_id).first()

        return {
            "company": {
                "id": company.id,
                "name": company.name,
                "active": company.active,
            },
            "services": services,
            # Compatibility for older customer UI consumers while the service
            # list is the canonical billing representation.
            "subscription": ai_service,
            "summary": {
                "agents": len(agents),
                "active_agents": sum(1 for item in agents if item.enabled),
                "conversations": db.query(AIConversation).filter(
                    AIConversation.company_id == company_id
                ).count(),
                "requests": int(usage[0] or 0),
                "tokens": int(usage[1] or 0),
                "knowledge_documents": db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.company_id == company_id,
                    KnowledgeDocument.enabled.is_(True),
                ).count(),
                "channels": len(channels),
                "integrations": len(integrations),
            },
            "channels": [
                {
                    "id": item.id,
                    "agent_id": item.agent_id,
                    "type": item.channel_type,
                    "enabled": item.enabled,
                    "config": public_config(item.config),
                    "configured_secret_fields": configured_secret_fields(item.config),
                }
                for item in channels
            ],
            "integrations": [
                {
                    "id": item.id,
                    "type": item.integration_type,
                    "name": item.name,
                    "enabled": item.enabled,
                    "config": public_config(item.config),
                    "configured_secret_fields": configured_secret_fields(item.config),
                }
                for item in integrations
            ],
        }
    finally:
        db.close()
