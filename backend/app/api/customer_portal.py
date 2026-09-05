from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.app.core.config_secrets import configured_secret_fields, public_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_user
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIUsage
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.knowledge.models import KnowledgeDocument
from backend.app.modules.solutions.catalog import SERVICE_CATALOG
from backend.app.modules.solutions.portal import (
    BUSINESS_CAPABILITY_MODULES,
    build_customer_portal_navigation,
)

router = APIRouter(prefix="/customer", tags=["Customer Portal"])

MANAGER_ROLES = {"owner", "admin", "manager"}


def _plain_limit(value):
    if value in (None, 0, "0"):
        return 0
    try:
        text = format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError, TypeError):
        return value
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _plan_limits(plan: ServicePlan) -> dict:
    return {key: _plain_limit(value) for key, value in (plan.limits or {}).items()}


def _service_data(db, subscription: ServiceSubscription, plan: ServicePlan) -> dict:
    usage = {}
    for metric, limit in (plan.limits or {}).items():
        usage[metric] = {
            "used": service_limits.used(db, subscription, metric),
            "limit": _plain_limit(limit),
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
            "limits": _plan_limits(plan),
        },
        "usage": usage,
    }


def _staff_overview(db, current_user: User, company: Company) -> dict:
    agents = db.query(AIAgent).filter(AIAgent.company_id == company.id).all()
    channels = db.query(AgentChannel).filter(AgentChannel.company_id == company.id).all()
    return {
        "company": {
            "id": company.id,
            "name": company.name,
            "active": company.active,
        },
        "services": [],
        "subscription": None,
        "portal": {
            "access_level": "staff",
            "navigation": [
                {
                    "id": "dashboard",
                    "label": "Overview",
                    "loader": "dashboard",
                    "group": "Workspace",
                }
            ],
            "active_services": [],
            "capabilities": [],
        },
        "billing": {},
        "summary": {
            "agents": len(agents),
            "active_agents": sum(1 for item in agents if item.enabled),
            "channels": len(channels),
            "active_channels": sum(1 for item in channels if item.enabled),
        },
        "channels": [],
        "integrations": [],
    }


@router.get("/overview")
def overview(current_user: User = Depends(require_customer_user)):
    db = SessionLocal()
    try:
        company_id = current_user.company_id
        company = db.query(Company).filter(Company.id == company_id).first()

        if current_user.role not in MANAGER_ROLES:
            return _staff_overview(db, current_user, company)

        service_rows = (
            db.query(ServiceSubscription, ServicePlan)
            .join(ServicePlan, ServicePlan.id == ServiceSubscription.plan_id)
            .filter(ServiceSubscription.company_id == company_id)
            .order_by(ServiceSubscription.service_code.asc())
            .all()
        )
        services = [_service_data(db, subscription, plan) for subscription, plan in service_rows]
        ai_service = next((x for x in services if x["service_code"] == "ai_agents"), None)

        enabled_module_rows = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id == company_id,
                CompanyModule.enabled.is_(True),
            )
            .all()
        )
        enabled_modules = {item.module_name for item in enabled_module_rows}
        active_service_codes = [
            item["service_code"] for item in services if item["status"] == "active"
        ]
        navigation = build_customer_portal_navigation(
            active_service_codes,
            enabled_modules,
        )
        navigation.insert(
            max(len(navigation) - 1, 1),
            {
                "id": "users",
                "label": "Users",
                "loader": "users",
                "group": "Account",
            },
        )

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
            "subscription": ai_service,
            "portal": {
                "access_level": "manager",
                "navigation": navigation,
                "active_services": active_service_codes,
                "capabilities": sorted(
                    enabled_modules.intersection(BUSINESS_CAPABILITY_MODULES)
                ),
            },
            "billing": {
                "online_payments_enabled": False,
                "payment_provider": None,
                "payment_method": None,
            },
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
                "active_channels": sum(1 for item in channels if item.enabled),
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
