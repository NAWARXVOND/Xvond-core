from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIUsage
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration

router = APIRouter(prefix="/admin/company-view", tags=["Xvond Admin - Company View"])


@router.get("/{company_id}")
def company_full_view(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        users = db.query(User).filter(User.company_id == company_id).all()
        modules = db.query(CompanyModule).filter(CompanyModule.company_id == company_id).all()
        agents = db.query(AIAgent).filter(AIAgent.company_id == company_id).all()
        channels = db.query(AgentChannel).filter(AgentChannel.company_id == company_id).all()
        integrations = db.query(CompanyIntegration).filter(
            CompanyIntegration.company_id == company_id
        ).all()

        service_rows = (
            db.query(ServiceSubscription, ServicePlan)
            .join(ServicePlan, ServicePlan.id == ServiceSubscription.plan_id)
            .filter(ServiceSubscription.company_id == company_id)
            .order_by(ServiceSubscription.service_code.asc())
            .all()
        )
        services = [
            {
                "id": subscription.id,
                "service_code": subscription.service_code,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "plan": {
                    "id": plan.id,
                    "name": plan.name,
                    "tier": plan.tier,
                    "monthly_price": plan.monthly_price,
                    "currency": plan.currency,
                    "limits": plan.limits or {},
                    "enabled": plan.enabled,
                },
            }
            for subscription, plan in service_rows
        ]

        # Compatibility for existing admin cards while they migrate to the
        # service list: the AI Agents service represents the runtime plan.
        ai_service = next((item for item in services if item["service_code"] == "ai_agents"), None)
        subscription_compat = None
        if ai_service is not None:
            subscription_compat = {
                "id": ai_service["id"],
                "status": ai_service["status"],
                "current_period_start": ai_service["current_period_start"],
                "current_period_end": ai_service["current_period_end"],
                "plan": {
                    "id": ai_service["plan"]["id"],
                    "name": ai_service["plan"]["name"],
                    "price": ai_service["plan"]["monthly_price"],
                    "currency": ai_service["plan"]["currency"],
                },
            }

        conversation_count = db.query(func.count(AIConversation.id)).filter(
            AIConversation.company_id == company_id
        ).scalar()
        usage = db.query(
            func.count(AIUsage.id),
            func.coalesce(func.sum(AIUsage.total_tokens), 0),
            func.coalesce(func.sum(AIUsage.provider_cost), 0),
        ).filter(AIUsage.company_id == company_id).first()

        return {
            "company": {
                "id": company.id,
                "name": company.name,
                "active": company.active,
                "created_at": company.created_at,
            },
            "users": [
                {
                    "id": item.id,
                    "email": item.email,
                    "full_name": item.full_name,
                    "role": item.role,
                    "active": item.active,
                }
                for item in users
            ],
            "modules": [
                {"name": item.module_name, "enabled": item.enabled}
                for item in modules
            ],
            "agents": [
                {
                    "id": item.id,
                    "name": item.name,
                    "provider": item.provider,
                    "model": item.model,
                    "enabled": item.enabled,
                }
                for item in agents
            ],
            "channels": [
                {
                    "id": item.id,
                    "agent_id": item.agent_id,
                    "type": item.channel_type,
                    "enabled": item.enabled,
                }
                for item in channels
            ],
            "integrations": [
                {
                    "id": item.id,
                    "type": item.integration_type,
                    "name": item.name,
                    "enabled": item.enabled,
                }
                for item in integrations
            ],
            "services": services,
            "subscription": subscription_compat,
            "analytics": {
                "conversations": conversation_count or 0,
                "ai_requests": usage[0] if usage else 0,
                "tokens": usage[1] if usage else 0,
                "provider_cost": usage[2] if usage else 0,
            },
        }
    finally:
        db.close()
