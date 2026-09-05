from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.admin_ai_employee import _ensure_module, _select_model
from backend.app.api.admin_company_profile import sync_company_business_knowledge
from backend.app.core.config_secrets import merge_config, reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_profile import CompanyProfile
from backend.app.models.user import User
from backend.app.modules.ai_agent.factory_models import AgentConfig
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.ai_agent.profile_models import AIAgentProfile
from backend.app.modules.channels.models import AgentChannel

router = APIRouter(prefix="/admin/ai-employee-profile", tags=["Xvond Admin - AI Employee Profile"])


DEFAULT_CUSTOMER_CONTROLS = {
    "can_enable_disable": True,
    "can_view_conversations": True,
    "can_view_usage": True,
    "can_edit_prompt": False,
    "can_change_provider": False,
    "can_change_model": False,
}

DIALECTS = {
    "auto": "Automatically mirror the customer's natural dialect/register. If the customer writes colloquial Arabic, reply in the closest matching colloquial dialect and do not switch to Modern Standard Arabic unless the customer uses it.",
    "msa": "Always use natural Modern Standard Arabic (فصحى), regardless of the customer's Arabic dialect.",
    "omani": "Use natural Omani Arabic while remaining clear and professional.",
    "gulf": "Use natural Gulf Arabic while remaining clear and professional.",
    "saudi": "Use natural Saudi Arabic while remaining clear and professional.",
    "emirati": "Use natural Emirati Arabic while remaining clear and professional.",
    "levantine": "Use natural Levantine/Shami Arabic while remaining clear and professional.",
    "egyptian": "Use natural Egyptian Arabic while remaining clear and professional.",
}


class EmployeeProfileUpdate(BaseModel):
    name: str
    reply_language: str = "auto"
    dialect: str = "auto"
    conversation_style: str = "professional_friendly"
    greeting: str | None = None
    instructions: str | None = None
    business_name: str | None = None
    business_type: str | None = None


def _clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _dialect(value: str | None) -> str:
    value = str(value or "auto").strip().lower()
    if value not in DIALECTS:
        raise HTTPException(400, "Unsupported dialect")
    return value


def _company_profile(db, company_id: int) -> CompanyProfile | None:
    return db.query(CompanyProfile).filter(CompanyProfile.company_id == company_id).first()


def _company_business_type(db, company: Company, data: EmployeeProfileUpdate | None = None) -> str | None:
    profile = _company_profile(db, company.id)
    if profile is not None and profile.business_type:
        return profile.business_type
    return _clean(data.business_type) if data is not None else None


def _profile_prompt(company_name: str, data: EmployeeProfileUpdate) -> str:
    styles = {
        "professional_friendly": "Use a professional, friendly and natural conversational style.",
        "professional": "Use a polished professional style.",
        "warm": "Use a warm, conversational style while remaining professional.",
        "concise": "Be concise and direct while remaining helpful.",
    }
    dialect = _dialect(data.dialect)
    greeting_rule = (
        f"Preferred opening greeting: {data.greeting.strip()}"
        if _clean(data.greeting)
        else "Use a short natural greeting that identifies the business when appropriate; do not repeat it mechanically."
    )
    return f"""You are a customer-facing AI employee representing {company_name}.
You may serve customers through any connected Xvond channel. The channel is only the communication surface; your identity, knowledge and business operations are shared.

KNOWLEDGE USE:
Treat CORE COMPANY INFORMATION as the canonical source for identity, official contact details, website, locations, working hours, languages and other structured company facts.
Combine it with all relevant supplementary knowledge retrieved for the current request, including curated manual knowledge, PDFs and website content. Do not answer from only one source when multiple relevant sources are supplied.
If a curated manual fact conflicts with imported PDF or website text on a secondary detail, prefer the curated manual fact. If supporting imported sources conflict and the authoritative sources do not resolve it, do not guess.
Use partial verified knowledge intelligently: answer the part you can support, and never pretend that the entire subject is unknown just because one requested detail is missing.

SMART FALLBACK:
When a requested detail is not available, do not expose internal limitations with robotic phrases such as "I have no details", "the information is not in my knowledge", or "I cannot find this in the database".
First give any useful verified information that directly helps with the customer's intent.
If the missing detail genuinely requires confirmation and a verified company contact method exists, offer the most relevant contact method naturally and briefly. Prefer the channel or contact method configured by the business for that purpose when available; otherwise use the verified company contact information.
Do not dump every phone number, email address, website and contact option at once. Give only the most useful next step unless the customer asks for all contact methods.
If no verified answer and no verified next step exist, say briefly and naturally that this specific detail needs confirmation, without mentioning knowledge bases, prompts, tools, databases or system limitations.
Never manufacture a confident answer merely to avoid saying that a detail needs confirmation.

CAPABILITY BOUNDARY:
Use only business operations that are actually made available to you in the current turn.
If an operation such as booking, callback, quotation, order creation, cancellation, rescheduling or live handoff is not available, never claim or imply that you can perform it and do not collect customer fields for that unavailable operation.
When the customer simply asks for a phone number, contact method, responsible person, team member, support or sales contact, and verified contact details are present in company information, give the relevant verified contact detail directly and naturally. Do not turn a contact request into a booking, callback or lead form unless that exact operation is available and the customer asked for it.
Current configured business operations and their destinations are authoritative. Do not follow obsolete booking/order mode instructions from older configuration.
Never invent business facts or claim an operation succeeded unless the connected operation returned success.

CONVERSATION QUALITY:
Understand short follow-ups from the existing conversation context instead of restarting or interrogating the customer.
Ask only for information that is genuinely needed for the customer's current intent or for an available operation.
Prefer a direct useful answer over unnecessary questions. Never make the customer repeat information already provided.
Keep the conversation coherent: do not repeat the company introduction, greeting, service list or contact details unless they are relevant to the current message.
When the customer asks a broad question, summarize the relevant answer first and offer one useful next step rather than overwhelming them with every fact you know.
{styles.get(data.conversation_style, styles['professional_friendly'])}
Reply language policy: {data.reply_language}. When automatic, match the customer's language.
Dialect policy: {dialect}. {DIALECTS[dialect]}
When a fixed Arabic dialect is selected, keep that dialect consistently even if the customer uses another Arabic dialect. When dialect is automatic, mirror the customer's normal register naturally rather than defaulting to formal Arabic.
{greeting_rule}
Additional behavior instructions: {_clean(data.instructions) or 'None.'}""".strip()


def _setup_from_channels(channels):
    for channel in channels:
        config = reveal_config(channel.config) or {}
        setup = config.get("employee_setup")
        if isinstance(setup, dict) and setup:
            return dict(setup)
    return {}


def _profile_payload(db, company: Company, data: EmployeeProfileUpdate) -> dict:
    return {
        "business_name": company.name,
        "business_type": _company_business_type(db, company, data),
        "reply_language": data.reply_language,
        "conversation_style": data.conversation_style,
        "greeting": _clean(data.greeting),
        "instructions": _clean(data.instructions),
    }


def _upsert_profile(db, company: Company, agent: AIAgent, data: EmployeeProfileUpdate) -> AIAgentProfile:
    values = _profile_payload(db, company, data)
    row = db.query(AIAgentProfile).filter(AIAgentProfile.agent_id == agent.id).first()
    if row is None:
        row = AIAgentProfile(company_id=company.id, agent_id=agent.id, **values)
        db.add(row)
    else:
        row.company_id = company.id
        for key, value in values.items():
            setattr(row, key, value)
    return row


def _ensure_agent_config(db, agent: AIAgent) -> AgentConfig:
    row = db.query(AgentConfig).filter(AgentConfig.agent_id == agent.id).first()
    if row is None:
        row = AgentConfig(
            agent_id=agent.id,
            agent_type="custom",
            settings={"dialect": "auto"},
            capabilities={},
            customer_controls=dict(DEFAULT_CUSTOMER_CONTROLS),
        )
        db.add(row)
        db.flush()
        return row

    settings = dict(row.settings or {})
    if "dialect" not in settings:
        settings["dialect"] = "auto"
        row.settings = settings

    controls = dict(DEFAULT_CUSTOMER_CONTROLS)
    controls.update(row.customer_controls or {})
    if controls != (row.customer_controls or {}):
        row.customer_controls = controls
    return row


def _set_agent_dialect(db, agent: AIAgent, dialect: str) -> AgentConfig:
    row = _ensure_agent_config(db, agent)
    settings = dict(row.settings or {})
    settings["dialect"] = _dialect(dialect)
    row.settings = settings
    return row


def _agent_dialect(db, agent: AIAgent, channels=None) -> str:
    row = _ensure_agent_config(db, agent)
    value = str((row.settings or {}).get("dialect") or "").strip().lower()
    if value in DIALECTS:
        return value
    setup = _setup_from_channels(channels or [])
    legacy = str(setup.get("dialect") or "auto").strip().lower()
    return legacy if legacy in DIALECTS else "auto"


def _backfill_profile(db, company: Company, agent: AIAgent, channels) -> AIAgentProfile:
    row = db.query(AIAgentProfile).filter(AIAgentProfile.agent_id == agent.id).first()
    if row is not None:
        row.business_name = company.name
        company_type = _company_business_type(db, company)
        if company_type:
            row.business_type = company_type
        return row
    setup = _setup_from_channels(channels)
    row = AIAgentProfile(
        company_id=company.id,
        agent_id=agent.id,
        business_name=company.name,
        business_type=_company_business_type(db, company) or _clean(setup.get("business_type")),
        reply_language=setup.get("reply_language") or "auto",
        conversation_style=setup.get("conversation_style") or "professional_friendly",
        greeting=_clean(setup.get("greeting")),
        instructions=_clean(setup.get("instructions")),
    )
    db.add(row)
    db.flush()
    return row


@router.post("/companies/{company_id}")
def create_profile_employee(company_id: int, data: EmployeeProfileUpdate, current_admin: User = Depends(require_xvond_admin)):
    """Create a channel-independent AI employee in draft mode."""
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
            enabled=False,
        )
        db.add(agent)
        db.flush()
        _upsert_profile(db, company, agent, data)
        _set_agent_dialect(db, agent, data.dialect)

        company_profile = _company_profile(db, company_id)
        if company_profile is not None:
            sync_company_business_knowledge(db, company, company_profile)

        db.commit()
        db.refresh(agent)
        payload = _profile_payload(db, company, data)
        payload["dialect"] = _dialect(data.dialect)
        return {
            "status": "created",
            "lifecycle": "draft",
            "agent_id": agent.id,
            "profile": payload,
        }
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
        channels = (
            db.query(AgentChannel)
            .filter(AgentChannel.company_id == company_id, AgentChannel.agent_id == agent_id)
            .order_by(AgentChannel.id.asc())
            .all()
        )
        profile = _backfill_profile(db, company, agent, channels)
        dialect = _agent_dialect(db, agent, channels)
        db.commit()
        return {
            "agent_id": agent.id,
            "name": agent.name,
            "business_name": company.name,
            "business_type": _company_business_type(db, company) or profile.business_type or "",
            "reply_language": profile.reply_language or "auto",
            "dialect": dialect,
            "conversation_style": profile.conversation_style or "professional_friendly",
            "greeting": profile.greeting or "",
            "instructions": profile.instructions or "",
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
        profile = _upsert_profile(db, company, agent, data)
        _set_agent_dialect(db, agent, data.dialect)
        setup = {
            "business_name": company.name,
            "business_type": profile.business_type,
            "reply_language": profile.reply_language,
            "dialect": _dialect(data.dialect),
            "conversation_style": profile.conversation_style,
            "greeting": profile.greeting,
            "instructions": profile.instructions,
        }
        channels = db.query(AgentChannel).filter(
            AgentChannel.company_id == company_id,
            AgentChannel.agent_id == agent_id,
        ).all()
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
