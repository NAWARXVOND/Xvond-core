from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeChunk, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service
from backend.app.modules.providers.models import AIModelRecord, AIProviderRecord, CompanyAIProfile
from backend.app.modules.tools.models import AgentToolAssignment

router = APIRouter(prefix="/admin/ai-employees", tags=["Xvond Admin - AI Employees"])
INTERNAL_MODE = "xvond_internal"


class AIEmployeeCreate(BaseModel):
    channel: str = "whatsapp"
    name: str | None = None
    business_name: str | None = None
    business_type: str | None = None
    business_description: str | None = None
    working_hours: str | None = None
    reply_language: str = "auto"
    business_information: str | None = None
    website: str | None = None
    booking_system: str | None = None
    order_system: str | None = None
    # Kept for backward-compatible payloads. These are not treated as connected systems.
    other_system: str | None = None
    monthly_usage_limit: int | None = Field(default=None, ge=1)
    instructions: str | None = None
    whatsapp: dict = Field(default_factory=dict)


class AIEmployeeUpdate(AIEmployeeCreate):
    pass


def _clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _mode(value):
    return INTERNAL_MODE if _clean(value) == INTERNAL_MODE else None


def _ensure_module(db, company_id, name):
    row = db.query(CompanyModule).filter(CompanyModule.company_id == company_id, CompanyModule.module_name == name).first()
    if row is None:
        row = CompanyModule(company_id=company_id, module_name=name, enabled=True)
        db.add(row)
    else:
        row.enabled = True
    return row


def _assign_tool(db, agent_id, name, enabled=True, config=None):
    row = db.query(AgentToolAssignment).filter(AgentToolAssignment.agent_id == agent_id, AgentToolAssignment.tool_name == name).first()
    if row:
        row.enabled = enabled
        row.config = config or {}
    else:
        db.add(AgentToolAssignment(agent_id=agent_id, tool_name=name, enabled=enabled, config=config or {}))


def _sync_capabilities(db, agent_id, data):
    _assign_tool(db, agent_id, "human_handoff", True, {"approval_required": False})
    _assign_tool(db, agent_id, "lead", True, {"approval_required": False})
    _assign_tool(db, agent_id, "booking", _mode(data.booking_system) == INTERNAL_MODE, {"approval_required": False, "mode": INTERNAL_MODE})
    _assign_tool(db, agent_id, "order", _mode(data.order_system) == INTERNAL_MODE, {"approval_required": False, "mode": INTERNAL_MODE})


def _select_model(db, company_id):
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
    if not row:
        raise HTTPException(400, "No enabled AI provider/model is configured")
    model, provider = row
    return provider.name, model.model_name


def _employee_prompt(company_name, data):
    booking = "XVOND_INTERNAL" if _mode(data.booking_system) == INTERNAL_MODE else "DISABLED"
    orders = "XVOND_INTERNAL" if _mode(data.order_system) == INTERNAL_MODE else "DISABLED"
    return f"""You are the full-service WhatsApp AI employee for {data.business_name or company_name}.
Handle customer questions, sales conversations and follow-ups naturally.
Business facts must come from COMPANY KNOWLEDGE or successful connected actions. Never invent prices, menu items, services, products, availability, stock, branches, policies, offers, delivery terms, hours, booking details or order status.
BOOKING MODE: {booking}. ORDER MODE: {orders}.
When BOOKING MODE is XVOND_INTERNAL, collect missing booking details progressively and use the booking tool. Never say a booking is confirmed unless the tool succeeds. When booking is DISABLED and the customer asks to create/change/cancel a booking, transfer to a human using human_handoff.
When ORDER MODE is XVOND_INTERNAL, collect missing order details progressively and use the order tool. Never say an order was placed unless the tool succeeds. When orders are DISABLED and the customer asks to create/change/cancel an order, transfer to a human using human_handoff.
Do not give a phone number as a substitute for human handoff. Human takeover is handled inside the conversation system.
Reply language policy: {data.reply_language}. Working hours: {data.working_hours or 'not specified'}.
Additional instructions: {data.instructions or 'None.'}""".strip()


def _doc(db, agent_id, title):
    return (
        db.query(KnowledgeDocument)
        .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
        .filter(AgentKnowledge.agent_id == agent_id, KnowledgeDocument.title == title)
        .first()
    )


def _add_doc(db, company_id, agent_id, title, source_type, content):
    doc = KnowledgeDocument(company_id=company_id, title=title, source_type=source_type, content=content, enabled=True)
    db.add(doc)
    db.flush()
    knowledge_service.rebuild_document_index(db, doc)
    db.add(AgentKnowledge(agent_id=agent_id, document_id=doc.id, enabled=True))
    return doc


def _upsert_doc(db, company_id, agent_id, title, source_type, content):
    doc = _doc(db, agent_id, title)
    if not content:
        if doc:
            db.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id, AgentKnowledge.document_id == doc.id).delete(synchronize_session=False)
            db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete(synchronize_session=False)
            db.delete(doc)
        return
    if doc:
        doc.content = content
        doc.source_type = source_type
        doc.enabled = True
        link = db.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id, AgentKnowledge.document_id == doc.id).first()
        if link:
            link.enabled = True
        knowledge_service.rebuild_document_index(db, doc)
    else:
        _add_doc(db, company_id, agent_id, title, source_type, content)


def _setup(company, data):
    return {
        "business_name": _clean(data.business_name) or company.name,
        "business_type": _clean(data.business_type),
        "business_description": _clean(data.business_description),
        "working_hours": _clean(data.working_hours),
        "reply_language": data.reply_language,
        "business_information": _clean(data.business_information),
        "website": _clean(data.website),
        "booking_system": _mode(data.booking_system),
        "order_system": _mode(data.order_system),
        "instructions": _clean(data.instructions),
    }


def _profile(company, data):
    return "\n".join([
        f"Business name: {_clean(data.business_name) or company.name}",
        f"Business type: {_clean(data.business_type) or 'Not specified'}",
        f"Business description: {_clean(data.business_description) or 'Not specified'}",
        f"Working hours: {_clean(data.working_hours) or 'Not specified'}",
        f"Reply language: {data.reply_language}",
    ])


@router.post("/companies/{company_id}")
def create_ai_employee(company_id: int, data: AIEmployeeCreate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(404, "Company not found")
        if db.query(AgentChannel).filter(AgentChannel.company_id == company_id, AgentChannel.channel_type == "whatsapp").first():
            raise HTTPException(409, "This company already has a WhatsApp AI employee")
        for name in ("ai_agent", "knowledge", "tools"):
            _ensure_module(db, company_id, name)
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
        _sync_capabilities(db, agent.id, data)
        _add_doc(db, company_id, agent.id, "Business Profile", "business_profile", _profile(company, data))
        if _clean(data.business_information):
            _add_doc(db, company_id, agent.id, "Business Information", "general", data.business_information.strip())
        if _clean(data.website):
            _add_doc(db, company_id, agent.id, "Business Website", "website_reference", f"Official website: {data.website.strip()}")
        config = dict(data.whatsapp or {})
        config["employee_setup"] = _setup(company, data)
        channel = AgentChannel(company_id=company_id, agent_id=agent.id, channel_type="whatsapp", config=config, enabled=False)
        db.add(channel)
        db.commit()
        return {"status": "created", "employee": {"id": agent.id, "channel_id": channel.id}}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.get("/companies/{company_id}/{agent_id}/settings")
def get_settings(company_id: int, agent_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
        channel = db.query(AgentChannel).filter(AgentChannel.agent_id == agent_id, AgentChannel.company_id == company_id).first()
        if not agent or not channel:
            raise HTTPException(404, "AI employee not found")
        setup = dict((channel.config or {}).get("employee_setup") or {})
        info = _doc(db, agent_id, "Business Information")
        website = _doc(db, agent_id, "Business Website")
        profile = _doc(db, agent_id, "Business Profile")
        fallback = {}
        if profile:
            for line in profile.content.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    fallback[key.strip()] = value.strip()
        return {
            "name": agent.name,
            "business_name": setup.get("business_name") or fallback.get("Business name") or "",
            "business_type": setup.get("business_type") or fallback.get("Business type") or "",
            "business_description": setup.get("business_description") or fallback.get("Business description") or "",
            "working_hours": setup.get("working_hours") or fallback.get("Working hours") or "",
            "reply_language": setup.get("reply_language") or fallback.get("Reply language") or "auto",
            "business_information": setup.get("business_information") or (info.content if info else ""),
            "website": setup.get("website") or (website.content.removeprefix("Official website: ") if website else ""),
            "booking_system": _mode(setup.get("booking_system")) or "",
            "order_system": _mode(setup.get("order_system")) or "",
            "instructions": setup.get("instructions") or "",
        }
    finally:
        db.close()


@router.put("/companies/{company_id}/{agent_id}/settings")
def update_settings(company_id: int, agent_id: int, data: AIEmployeeUpdate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
        channel = db.query(AgentChannel).filter(AgentChannel.agent_id == agent_id, AgentChannel.company_id == company_id).first()
        if not company or not agent or not channel:
            raise HTTPException(404, "AI employee not found")
        agent.name = _clean(data.name) or agent.name
        agent.system_prompt = _employee_prompt(company.name, data)
        _sync_capabilities(db, agent_id, data)
        _upsert_doc(db, company_id, agent_id, "Business Profile", "business_profile", _profile(company, data))
        _upsert_doc(db, company_id, agent_id, "Business Information", "general", _clean(data.business_information))
        _upsert_doc(db, company_id, agent_id, "Business Website", "website_reference", f"Official website: {data.website.strip()}" if _clean(data.website) else None)
        config = dict(channel.config or {})
        config["employee_setup"] = _setup(company, data)
        channel.config = config
        db.commit()
        return {"status": "updated"}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def _delete_direct_agent_fk_rows(db, agent_id: int):
    rows = db.execute(text("""SELECT DISTINCT tc.table_name,kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name AND tc.constraint_schema=kcu.constraint_schema JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name AND ccu.constraint_schema=tc.constraint_schema WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public' AND ccu.table_schema='public' AND ccu.table_name='ai_agents' AND ccu.column_name='id'""")).all()
    for table_name, column_name in rows:
        if table_name != "ai_agents":
            db.execute(text(f'DELETE FROM "{table_name}" WHERE "{column_name}"=:agent_id'), {"agent_id": agent_id})


@router.delete("/companies/{company_id}/{agent_id}")
def delete_ai_employee(company_id: int, agent_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
        if not agent:
            raise HTTPException(404, "AI employee not found")
        channel = db.query(AgentChannel).filter(AgentChannel.agent_id == agent_id, AgentChannel.company_id == company_id).first()
        if channel and channel.enabled:
            raise HTTPException(409, "Disconnect/deactivate the live channel before permanently deleting this AI employee")
        conversation_ids = [row[0] for row in db.query(AIConversation.id).filter(AIConversation.agent_id == agent_id).all()]
        if conversation_ids:
            db.query(AIMessage).filter(AIMessage.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        links = db.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id).all()
        document_ids = [link.document_id for link in links]
        _delete_direct_agent_fk_rows(db, agent_id)
        for document_id in document_ids:
            if not db.query(AgentKnowledge).filter(AgentKnowledge.document_id == document_id).first():
                db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).delete(synchronize_session=False)
                db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id, KnowledgeDocument.company_id == company_id).delete(synchronize_session=False)
        db.execute(text("DELETE FROM ai_agents WHERE id=:agent_id AND company_id=:company_id"), {"agent_id": agent_id, "company_id": company_id})
        db.commit()
        return {"status": "deleted"}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
