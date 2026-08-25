from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.knowledge.service import KnowledgeService
from backend.app.modules.providers.models import AIModelRecord, AIProviderRecord, CompanyAIProfile

router = APIRouter(prefix="/admin/ai-employees", tags=["Xvond Admin - AI Employees"])
knowledge_service = KnowledgeService()


class AIEmployeeCreate(BaseModel):
    channel: str
    name: str | None = None
    business_name: str | None = None
    business_type: str | None = None
    business_description: str | None = None
    working_hours: str | None = None
    reply_language: str = "auto"
    business_information: str | None = None
    website: str | None = None
    human_handoff: str | None = None
    booking_system: str | None = None
    order_system: str | None = None
    other_system: str | None = None
    monthly_usage_limit: int | None = Field(default=None, ge=1)
    instructions: str | None = None
    whatsapp: dict = Field(default_factory=dict)


def _clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _select_model(db, company_id: int):
    profile = db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id == company_id).first()
    if profile and profile.default_provider and profile.default_model:
        return profile.default_provider, profile.default_model
    row = (
        db.query(AIModelRecord, AIProviderRecord)
        .join(AIProviderRecord, AIProviderRecord.name == AIModelRecord.provider_name)
        .filter(AIModelRecord.enabled.is_(True), AIProviderRecord.enabled.is_(True))
        .order_by(AIProviderRecord.priority.asc(), AIModelRecord.id.asc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=400, detail="No enabled AI provider/model is configured")
    model, provider = row
    return provider.name, model.model_name


def _employee_prompt(company_name: str, data: AIEmployeeCreate):
    return f"""You are the full-service WhatsApp AI employee for {data.business_name or company_name}.
Handle customer conversations from start to finish: questions, sales, bookings, orders, follow-ups and human handoff.
Use connected knowledge as the source of truth for business facts.
Reply language policy: {data.reply_language}.
Working hours: {data.working_hours or 'not specified'}.
When a real booking/order/integration tool is available, use it for the requested action.
Never claim an action succeeded unless the corresponding tool or integration succeeded.
If the required system is unavailable, continue helping and use human handoff when appropriate.
Human handoff destination/instructions: {data.human_handoff or 'not configured'}.
Additional instructions: {data.instructions or 'None.'}
""".strip()


def _add_knowledge(db, company_id: int, agent_id: int, title: str, source_type: str, content: str):
    document = KnowledgeDocument(
        company_id=company_id,
        title=title,
        source_type=source_type,
        content=content,
        enabled=True,
    )
    db.add(document)
    db.flush()
    knowledge_service.rebuild_document_index(db, document)
    db.add(AgentKnowledge(agent_id=agent_id, document_id=document.id, enabled=True))
    return document


def _add_integration(db, company_id: int, integration_type: str, name: str, value: str):
    integration = CompanyIntegration(
        company_id=company_id,
        integration_type=integration_type,
        name=name,
        config={"setup_reference": value, "provisioning_status": "needs_connection"},
        enabled=False,
    )
    db.add(integration)
    return integration


@router.post("/companies/{company_id}")
def create_ai_employee(company_id: int, data: AIEmployeeCreate, current_admin: User = Depends(require_xvond_admin)):
    if data.channel.strip().lower() != "whatsapp":
        raise HTTPException(status_code=400, detail="WhatsApp is the only employee channel enabled in this setup")

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        existing = db.query(AgentChannel).filter(
            AgentChannel.company_id == company_id,
            AgentChannel.channel_type == "whatsapp",
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="This company already has a WhatsApp AI employee")

        provider, model = _select_model(db, company_id)
        agent = AIAgent(
            company_id=company_id,
            name=_clean(data.name) or "WhatsApp AI Employee",
            description="Full-service WhatsApp AI employee",
            system_prompt=_employee_prompt(company.name, data),
            provider=provider,
            model=model,
            enabled=True,
        )
        db.add(agent)
        db.flush()

        profile_lines = [
            f"Business name: {_clean(data.business_name) or company.name}",
            f"Business type: {_clean(data.business_type) or 'Not specified'}",
            f"Business description: {_clean(data.business_description) or 'Not specified'}",
            f"Working hours: {_clean(data.working_hours) or 'Not specified'}",
            f"Reply language: {data.reply_language}",
            f"Human handoff: {_clean(data.human_handoff) or 'Not configured'}",
        ]
        _add_knowledge(db, company_id, agent.id, "Business Profile", "business_profile", "\n".join(profile_lines))

        if _clean(data.business_information):
            _add_knowledge(db, company_id, agent.id, "Business Information", "text", data.business_information.strip())
        if _clean(data.website):
            _add_knowledge(db, company_id, agent.id, "Business Website", "website_reference", f"Official website: {data.website.strip()}")

        integrations = []
        if _clean(data.booking_system):
            integrations.append(_add_integration(db, company_id, "booking", "Booking System", data.booking_system.strip()))
        if _clean(data.order_system):
            integrations.append(_add_integration(db, company_id, "orders", "Orders / Store System", data.order_system.strip()))
        if _clean(data.other_system):
            integrations.append(_add_integration(db, company_id, "custom", "Other Connected System", data.other_system.strip()))

        config = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in (data.whatsapp or {}).items()
            if value not in (None, "")
        }
        config["employee_setup"] = {
            "business_name": _clean(data.business_name) or company.name,
            "business_type": _clean(data.business_type),
            "working_hours": _clean(data.working_hours),
            "reply_language": data.reply_language,
            "human_handoff": _clean(data.human_handoff),
            "monthly_usage_limit": data.monthly_usage_limit,
        }
        channel_row = AgentChannel(
            company_id=company_id,
            agent_id=agent.id,
            channel_type="whatsapp",
            config=config,
            enabled=False,
        )
        db.add(channel_row)
        db.commit()
        db.refresh(agent)
        db.refresh(channel_row)

        return {
            "status": "created",
            "employee": {
                "id": agent.id,
                "name": agent.name,
                "channel": "whatsapp",
                "enabled": agent.enabled,
                "channel_enabled": channel_row.enabled,
                "channel_id": channel_row.id,
                "provider": agent.provider,
                "model": agent.model,
                "knowledge_provisioned": True,
                "integrations_created": len(integrations),
                "monthly_usage_limit": data.monthly_usage_limit,
            },
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
