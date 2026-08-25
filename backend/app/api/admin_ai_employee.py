from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage, AIUsage
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeChunk, KnowledgeDocument
from backend.app.modules.knowledge.service import KnowledgeService
from backend.app.modules.providers.models import AIModelRecord, AIProviderRecord, CompanyAIProfile
from backend.app.modules.tools.models import AgentToolAssignment, ToolApprovalRequest

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

def _clean(value): return value.strip() if isinstance(value, str) and value.strip() else None

def _ensure_module(db, company_id, module_name):
    row=db.query(CompanyModule).filter(CompanyModule.company_id==company_id,CompanyModule.module_name==module_name).first()
    if row is None: row=CompanyModule(company_id=company_id,module_name=module_name,enabled=True); db.add(row)
    else: row.enabled=True
    return row

def _select_model(db, company_id):
    profile=db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id==company_id).first()
    if profile and profile.default_provider and profile.default_model: return profile.default_provider,profile.default_model
    row=db.query(AIModelRecord,AIProviderRecord).join(AIProviderRecord,AIProviderRecord.name==AIModelRecord.provider_name).filter(AIModelRecord.enabled.is_(True),AIProviderRecord.enabled.is_(True)).order_by(AIProviderRecord.priority.asc(),AIModelRecord.id.asc()).first()
    if row is None: raise HTTPException(status_code=400,detail="No enabled AI provider/model is configured")
    model,provider=row; return provider.name,model.model_name

def _employee_prompt(company_name,data):
    return f"""You are the full-service WhatsApp AI employee for {data.business_name or company_name}.
Handle customer conversations from start to finish: questions, sales, bookings, orders, follow-ups and human handoff.
STRICT BUSINESS FACT RULES:
- COMPANY KNOWLEDGE supplied at runtime is the only source of truth for company-specific facts.
- Never invent, estimate, assume, generalize, or use outside knowledge for prices, services, products, availability, stock, branches, policies, offers, delivery terms, business hours, booking details, order status, or any other company fact.
- If a requested company fact is absent from COMPANY KNOWLEDGE and connected tool results, say you do not have that information and offer human handoff when configured.
- Preserve prices, currencies, names and conditions exactly as provided. Never add unlisted services or products.
Reply language policy: {data.reply_language}.
Working hours: {data.working_hours or 'not specified'}.
Use real connected tools for actions. Never claim booking, order, payment, cancellation, update or another action succeeded unless its tool returned success.
Human handoff destination/instructions: {data.human_handoff or 'not configured'}.
Additional instructions: {data.instructions or 'None.'}""".strip()

def _add_knowledge(db,company_id,agent_id,title,source_type,content):
    document=KnowledgeDocument(company_id=company_id,title=title,source_type=source_type,content=content,enabled=True); db.add(document); db.flush(); knowledge_service.rebuild_document_index(db,document); db.add(AgentKnowledge(agent_id=agent_id,document_id=document.id,enabled=True)); return document

def _add_integration(db,company_id,integration_type,name,value):
    integration=CompanyIntegration(company_id=company_id,integration_type=integration_type,name=name,config={"setup_reference":value,"provisioning_status":"needs_connection"},enabled=False); db.add(integration); return integration

@router.post("/companies/{company_id}")
def create_ai_employee(company_id:int,data:AIEmployeeCreate,current_admin:User=Depends(require_xvond_admin)):
    if data.channel.strip().lower()!="whatsapp": raise HTTPException(status_code=400,detail="WhatsApp is the only employee channel enabled in this setup")
    db=SessionLocal()
    try:
        company=db.query(Company).filter(Company.id==company_id).first()
        if company is None: raise HTTPException(status_code=404,detail="Company not found")
        if db.query(AgentChannel).filter(AgentChannel.company_id==company_id,AgentChannel.channel_type=="whatsapp").first() is not None: raise HTTPException(status_code=409,detail="This company already has a WhatsApp AI employee")
        _ensure_module(db,company_id,"ai_agent"); _ensure_module(db,company_id,"knowledge"); _ensure_module(db,company_id,"tools")
        if any((_clean(data.booking_system),_clean(data.order_system),_clean(data.other_system))): _ensure_module(db,company_id,"integrations")
        provider,model=_select_model(db,company_id)
        agent=AIAgent(company_id=company_id,name=_clean(data.name) or "WhatsApp AI Employee",description="Full-service WhatsApp AI employee",system_prompt=_employee_prompt(company.name,data),provider=provider,model=model,enabled=True); db.add(agent); db.flush()
        profile=[f"Business name: {_clean(data.business_name) or company.name}",f"Business type: {_clean(data.business_type) or 'Not specified'}",f"Business description: {_clean(data.business_description) or 'Not specified'}",f"Working hours: {_clean(data.working_hours) or 'Not specified'}",f"Reply language: {data.reply_language}",f"Human handoff: {_clean(data.human_handoff) or 'Not configured'}"]
        _add_knowledge(db,company_id,agent.id,"Business Profile","business_profile","\n".join(profile))
        if _clean(data.business_information): _add_knowledge(db,company_id,agent.id,"Business Information","text",data.business_information.strip())
        if _clean(data.website): _add_knowledge(db,company_id,agent.id,"Business Website","website_reference",f"Official website: {data.website.strip()}")
        integrations=[]
        if _clean(data.booking_system): integrations.append(_add_integration(db,company_id,"booking","Booking System",data.booking_system.strip()))
        if _clean(data.order_system): integrations.append(_add_integration(db,company_id,"orders","Orders / Store System",data.order_system.strip()))
        if _clean(data.other_system): integrations.append(_add_integration(db,company_id,"custom","Other Connected System",data.other_system.strip()))
        config={k:(v.strip() if isinstance(v,str) else v) for k,v in (data.whatsapp or {}).items() if v not in (None,"")}; config["employee_setup"]={"business_name":_clean(data.business_name) or company.name,"business_type":_clean(data.business_type),"working_hours":_clean(data.working_hours),"reply_language":data.reply_language,"human_handoff":_clean(data.human_handoff),"monthly_usage_limit":data.monthly_usage_limit}
        channel=AgentChannel(company_id=company_id,agent_id=agent.id,channel_type="whatsapp",config=config,enabled=False); db.add(channel); db.commit(); db.refresh(agent); db.refresh(channel)
        return {"status":"created","employee":{"id":agent.id,"name":agent.name,"channel":"whatsapp","channel_id":channel.id,"provider":agent.provider,"model":agent.model,"knowledge_provisioned":True,"integrations_created":len(integrations),"monthly_usage_limit":data.monthly_usage_limit}}
    except HTTPException: db.rollback(); raise
    except Exception: db.rollback(); raise
    finally: db.close()

@router.delete("/companies/{company_id}/{agent_id}")
def delete_ai_employee(company_id:int,agent_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        agent=db.query(AIAgent).filter(AIAgent.id==agent_id,AIAgent.company_id==company_id).first()
        if agent is None: raise HTTPException(status_code=404,detail="AI employee not found")
        channel=db.query(AgentChannel).filter(AgentChannel.agent_id==agent_id,AgentChannel.company_id==company_id).first()
        if channel and channel.enabled: raise HTTPException(status_code=409,detail="Disconnect/deactivate the live channel before permanently deleting this AI employee")
        conversation_ids=[x[0] for x in db.query(AIConversation.id).filter(AIConversation.agent_id==agent_id).all()]
        if conversation_ids: db.query(AIMessage).filter(AIMessage.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(ToolApprovalRequest).filter(ToolApprovalRequest.agent_id==agent_id).delete(synchronize_session=False)
        db.query(AIConversation).filter(AIConversation.agent_id==agent_id).delete(synchronize_session=False)
        db.query(AIUsage).filter(AIUsage.agent_id==agent_id).delete(synchronize_session=False)
        db.query(AgentToolAssignment).filter(AgentToolAssignment.agent_id==agent_id).delete(synchronize_session=False)
        links=db.query(AgentKnowledge).filter(AgentKnowledge.agent_id==agent_id).all(); document_ids=[x.document_id for x in links]
        db.query(AgentKnowledge).filter(AgentKnowledge.agent_id==agent_id).delete(synchronize_session=False)
        for document_id in document_ids:
            other=db.query(AgentKnowledge).filter(AgentKnowledge.document_id==document_id).first()
            if other is None:
                db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id==document_id).delete(synchronize_session=False)
                db.query(KnowledgeDocument).filter(KnowledgeDocument.id==document_id,KnowledgeDocument.company_id==company_id).delete(synchronize_session=False)
        db.query(AgentChannel).filter(AgentChannel.agent_id==agent_id).delete(synchronize_session=False)
        db.delete(agent); db.commit()
        return {"status":"deleted","agent_id":agent_id}
    except HTTPException: db.rollback(); raise
    except Exception: db.rollback(); raise
    finally: db.close()
