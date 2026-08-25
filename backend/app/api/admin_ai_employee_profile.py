from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.admin_ai_employee import _ensure_module, _select_model
from backend.app.core.config_secrets import merge_config, reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.channels.models import AgentChannel

router = APIRouter(prefix="/admin/ai-employee-profile", tags=["Xvond Admin - AI Employee Profile"])


class EmployeeProfileUpdate(BaseModel):
    name: str
    business_name: str
    business_type: str | None = None
    reply_language: str = "auto"
    conversation_style: str = "professional_friendly"
    greeting: str | None = None
    instructions: str | None = None


def _clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _profile_prompt(company_name: str, data: EmployeeProfileUpdate) -> str:
    business_name = _clean(data.business_name) or company_name
    styles = {
        "professional_friendly": "Use a professional, friendly and natural conversational style.",
        "professional": "Use a polished professional style.",
        "warm": "Use a warm, conversational style while remaining professional.",
        "concise": "Be concise and direct while remaining helpful.",
    }
    greeting_rule = (
        f"Preferred opening greeting: {data.greeting.strip()}"
        if _clean(data.greeting)
        else "Use a short natural greeting that identifies the business when appropriate; do not repeat it mechanically."
    )
    return f"""You are the customer-facing AI employee representing {business_name}.
You may serve customers through any connected Xvond channel. The channel is only the communication surface; your identity, knowledge and business operations are shared.
Answer customer questions naturally and use only the business operations currently made available to you by Xvond.
Current configured business operations and their destinations are authoritative. Do not follow obsolete booking/order mode instructions from older configuration.
Never invent business facts or claim an operation succeeded unless the connected operation returned success.
{styles.get(data.conversation_style, styles['professional_friendly'])}
Reply language policy: {data.reply_language}. When automatic, match the customer's language and normal register.
{greeting_rule}
Additional behavior instructions: {_clean(data.instructions) or 'None.'}""".strip()


def _setup_from_channels(channels):
    for channel in channels:
        config = reveal_config(channel.config) or {}
        setup = config.get("employee_setup")
        if isinstance(setup, dict) and setup:
            return dict(setup)
    return {}


def _profile_payload(company: Company, data: EmployeeProfileUpdate) -> dict:
    return {
        "business_name": _clean(data.business_name) or company.name,
        "business_type": _clean(data.business_type),
        "reply_language": data.reply_language,
        "conversation_style": data.conversation_style,
        "greeting": _clean(data.greeting),
        "instructions": _clean(data.instructions),
    }


@router.post("/companies/{company_id}")
def create_profile_employee(company_id: int, data: EmployeeProfileUpdate, current_admin: User = Depends(require_xvond_admin)):
    """Create the channel-independent AI employee core.

    Website, WhatsApp and future channels are attached separately after this step.
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(404, "Company not found")
        for module_name in ("ai_agent", "knowledge", "tools"):
            _ensure_module(db, company_id, module_name)
        provider, model = _select_model(db, company_id)
        agent = AIAgent(
            company_id=company_id,
            name=_clean(data.name) or "AI Employee",
            description="Channel-independent AI business employee",
            system_prompt=_profile_prompt(company.name, data),
            provider=provider,
            model=model,
            enabled=True,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return {"status": "created", "agent_id": agent.id, "profile": _profile_payload(company, data)}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/companies/{company_id}/{agent_id}")
def get_profile(company_id: int, agent_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
        if not company or not agent:
            raise HTTPException(404, "AI employee not found")
        channels = db.query(AgentChannel).filter(AgentChannel.company_id == company_id, AgentChannel.agent_id == agent_id).order_by(AgentChannel.id.asc()).all()
        setup = _setup_from_channels(channels)
        return {
            "agent_id": agent.id,
            "name": agent.name,
            "business_name": setup.get("business_name") or company.name,
            "business_type": setup.get("business_type") or "",
            "reply_language": setup.get("reply_language") or "auto",
            "conversation_style": setup.get("conversation_style") or "professional_friendly",
            "greeting": setup.get("greeting") or "",
            "instructions": setup.get("instructions") or "",
        }
    finally:
        db.close()


@router.put("/companies/{company_id}/{agent_id}")
def update_profile(company_id: int, agent_id: int, data: EmployeeProfileUpdate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
        if not company or not agent:
            raise HTTPException(404, "AI employee not found")
        agent.name = _clean(data.name) or agent.name
        agent.system_prompt = _profile_prompt(company.name, data)
        setup = _profile_payload(company, data)
        channels = db.query(AgentChannel).filter(AgentChannel.company_id == company_id, AgentChannel.agent_id == agent_id).all()
        for channel in channels:
            channel.config = merge_config(channel.config, {"employee_setup": setup})
        db.commit()
        return {"status": "updated", "agent_id": agent.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
