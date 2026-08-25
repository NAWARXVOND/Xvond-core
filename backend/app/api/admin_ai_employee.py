from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.providers.models import AIModelRecord, AIProviderRecord, CompanyAIProfile

router = APIRouter(prefix="/admin/ai-employees", tags=["Xvond Admin - AI Employees"])


class AIEmployeeCreate(BaseModel):
    channel: str
    name: str | None = None
    business_description: str | None = None
    instructions: str | None = None
    whatsapp: dict = Field(default_factory=dict)


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


def _employee_prompt(company_name: str, business_description: str | None, instructions: str | None):
    return f"""You are the AI employee for {company_name}.
You handle the complete customer conversation from start to finish.
Answer questions using the company's connected knowledge and data.
When relevant and when the required system/tool is connected, you may create, confirm, change, cancel, or check bookings; create, confirm, or check orders; help with sales and product/service questions; and use any other company tools available to you.
Never claim that an action was completed unless the corresponding tool or integration actually succeeded.
If a booking/order system or required tool is not connected, continue helping normally and explain that the action needs staff assistance instead of inventing a result.
Use human handoff when the request needs a person or an action you cannot safely complete.
Business context: {business_description or 'Use connected company knowledge.'}
Additional instructions: {instructions or 'None.'}
""".strip()


@router.post("/companies/{company_id}")
def create_ai_employee(
    company_id: int,
    data: AIEmployeeCreate,
    current_admin: User = Depends(require_xvond_admin),
):
    channel = data.channel.strip().lower()
    if channel != "whatsapp":
        raise HTTPException(status_code=400, detail="WhatsApp is the only employee channel enabled in this setup")

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        existing = (
            db.query(AgentChannel)
            .filter(AgentChannel.company_id == company_id, AgentChannel.channel_type == "whatsapp")
            .first()
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="This company already has a WhatsApp AI employee")

        provider, model = _select_model(db, company_id)
        agent = AIAgent(
            company_id=company_id,
            name=(data.name or "WhatsApp AI Employee").strip(),
            description="Full-service WhatsApp AI employee",
            system_prompt=_employee_prompt(company.name, data.business_description, data.instructions),
            provider=provider,
            model=model,
            enabled=True,
        )
        db.add(agent)
        db.flush()

        config = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in (data.whatsapp or {}).items()
            if value not in (None, "")
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
