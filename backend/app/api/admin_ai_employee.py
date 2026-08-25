from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
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
router=APIRouter(prefix="/admin/ai-employees",tags=["Xvond Admin - AI Employees"]);knowledge_service=KnowledgeService()
class AIEmployeeCreate(BaseModel):
 channel:str="whatsapp";name:str|None=None;business_name:str|None=None;business_type:str|None=None;business_description:str|None=None;working_hours:str|None=None;reply_language:str="auto";business_information:str|None=None;website:str|None=None;booking_system:str|None=None;order_system:str|None=None;other_system:str|None=None;monthly_usage_limit:int|None=Field(default=None,ge=1);instructions:str|None=None;whatsapp:dict=Field(default_factory=dict)
class AIEmployeeUpdate(AIEmployeeCreate):pass
def _clean(v):return v.strip() if isinstance(v,str) and v.strip() else None
def _ensure_module(db,c,n):
 r=db.query(CompanyModule).filter(CompanyModule.company_id==c,CompanyModule.module_name==n).first()
 if r is None:r=CompanyModule(company_id=c,module_name=n,enabled=True);db.add(r)
 else:r.enabled=True
 return r
def _select_model(db,c):
 p=db.query(CompanyAIProfile).filter(CompanyAIProfile.company_id==c).first()
 if p and p.default_provider and p.default_model:return p.default_provider,p.default_model
 row=db.query(AIModelRecord,AIProviderRecord).join(AIProviderRecord,AIProviderRecord.name==AIModelRecord.provider_name).filter(AIModelRecord.enabled.is_(True),AIProviderRecord.enabled.is_(True)).order_by(AIProviderRecord.priority.asc(),AIModelRecord.id.asc()).first()
 if not row:raise HTTPException(400,"No enabled AI provider/model is configured")
 m,p=row;return p.name,m.model_name
def _employee_prompt(company_name,d):return f"""You are the full-service WhatsApp AI employee for {d.business_name or company_name}. Handle questions, sales, bookings, orders and follow-ups.
COMPANY KNOWLEDGE and connected tool results are the only source of truth for company facts. Never invent or estimate prices, services, products, availability, stock, branches, policies, offers, delivery terms, hours, booking details or order status. Preserve stored facts exactly. If a fact is absent, say you do not have it. Do not tell the customer to call a phone number for human handoff. Human takeover is controlled by the conversation system; when human mode is active, AI must not reply.
Reply language policy: {d.reply_language}. Working hours: {d.working_hours or 'not specified'}. Use real connected tools for actions and never claim an action succeeded unless its tool returned success. Additional instructions: {d.instructions or 'None.'}""".strip()
def _doc(db,a,title):return db.query(KnowledgeDocument).join(AgentKnowledge,AgentKnowledge.document_id==KnowledgeDocument.id).filter(AgentKnowledge.agent_id==a,KnowledgeDocument.title==title).first()
def _add_doc(db,c,a,title,stype,content):
 d=KnowledgeDocument(company_id=c,title=title,source_type=stype,content=content,enabled=True);db.add(d);db.flush();knowledge_service.rebuild_document_index(db,d);db.add(AgentKnowledge(agent_id=a,document_id=d.id,enabled=True));return d
def _upsert_doc(db,c,a,title,stype,content):
 d=_doc(db,a,title)
 if not content:
  if d:db.query(AgentKnowledge).filter(AgentKnowledge.agent_id==a,AgentKnowledge.document_id==d.id).delete(synchronize_session=False);db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id==d.id).delete(synchronize_session=False);db.delete(d)
 elif d:d.content=content;d.source_type=stype;d.enabled=True;knowledge_service.rebuild_document_index(db,d)
 else:_add_doc(db,c,a,title,stype,content)
def _sync_int(db,c,t,n,v):
 r=db.query(CompanyIntegration).filter(CompanyIntegration.company_id==c,CompanyIntegration.integration_type==t,CompanyIntegration.name==n).first()
 if v:
  if r:r.config={"setup_reference":v,"provisioning_status":"needs_connection"};r.enabled=False
  else:db.add(CompanyIntegration(company_id=c,integration_type=t,name=n,config={"setup_reference":v,"provisioning_status":"needs_connection"},enabled=False))
 elif r and not r.enabled:db.delete(r)
def _int_val(db,c,t):
 r=db.query(CompanyIntegration).filter(CompanyIntegration.company_id==c,CompanyIntegration.integration_type==t).order_by(CompanyIntegration.id.desc()).first();return (r.config or {}).get("setup_reference") if r else None
def _setup(company,d):return {"business_name":_clean(d.business_name) or company.name,"business_type":_clean(d.business_type),"business_description":_clean(d.business_description),"working_hours":_clean(d.working_hours),"reply_language":d.reply_language,"business_information":_clean(d.business_information),"website":_clean(d.website),"booking_system":_clean(d.booking_system),"order_system":_clean(d.order_system),"other_system":_clean(d.other_system),"monthly_usage_limit":d.monthly_usage_limit,"instructions":_clean(d.instructions)}
def _profile(company,d):return "\n".join([f"Business name: {_clean(d.business_name) or company.name}",f"Business type: {_clean(d.business_type) or 'Not specified'}",f"Business description: {_clean(d.business_description) or 'Not specified'}",f"Working hours: {_clean(d.working_hours) or 'Not specified'}",f"Reply language: {d.reply_language}"])
@router.post("/companies/{company_id}")
def create_ai_employee(company_id:int,data:AIEmployeeCreate,current_admin:User=Depends(require_xvond_admin)):
 db=SessionLocal()
 try:
  company=db.query(Company).filter(Company.id==company_id).first()
  if not company:raise HTTPException(404,"Company not found")
  if db.query(AgentChannel).filter(AgentChannel.company_id==company_id,AgentChannel.channel_type=="whatsapp").first():raise HTTPException(409,"This company already has a WhatsApp AI employee")
  for n in ("ai_agent","knowledge","tools"):_ensure_module(db,company_id,n)
  provider,model=_select_model(db,company_id);a=AIAgent(company_id=company_id,name=_clean(data.name) or "WhatsApp AI Employee",description="Full-service WhatsApp AI employee",system_prompt=_employee_prompt(company.name,data),provider=provider,model=model,enabled=True);db.add(a);db.flush();_add_doc(db,company_id,a.id,"Business Profile","business_profile",_profile(company,data))
  if _clean(data.business_information):_add_doc(db,company_id,a.id,"Business Information","text",data.business_information.strip())
  if _clean(data.website):_add_doc(db,company_id,a.id,"Business Website","website_reference",f"Official website: {data.website.strip()}")
  for t,n,v in (("booking","Booking System",_clean(data.booking_system)),("orders","Orders / Store System",_clean(data.order_system)),("custom","Other Connected System",_clean(data.other_system))):
   if v:_ensure_module(db,company_id,"integrations");_sync_int(db,company_id,t,n,v)
  cfg={k:v for k,v in (data.whatsapp or {}).items()};cfg["employee_setup"]=_setup(company,data);ch=AgentChannel(company_id=company_id,agent_id=a.id,channel_type="whatsapp",config=cfg,enabled=False);db.add(ch);db.commit();return {"status":"created","employee":{"id":a.id,"channel_id":ch.id}}
 except HTTPException:db.rollback();raise
 except Exception:db.rollback();raise
 finally:db.close()
@router.get("/companies/{company_id}/{agent_id}/settings")
def get_settings(company_id:int,agent_id:int,current_admin:User=Depends(require_xvond_admin)):
 db=SessionLocal()
 try:
  a=db.query(AIAgent).filter(AIAgent.id==agent_id,AIAgent.company_id==company_id).first();ch=db.query(AgentChannel).filter(AgentChannel.agent_id==agent_id,AgentChannel.company_id==company_id).first()
  if not a or not ch:raise HTTPException(404,"AI employee not found")
  s=dict((ch.config or {}).get("employee_setup") or {});info=_doc(db,agent_id,"Business Information");web=_doc(db,agent_id,"Business Website");p=_doc(db,agent_id,"Business Profile");fallback={}
  if p:
   for line in p.content.splitlines():
    if ":" in line:k,v=line.split(":",1);fallback[k.strip()]=v.strip()
  return {"name":a.name,"business_name":s.get("business_name") or fallback.get("Business name") or "","business_type":s.get("business_type") or fallback.get("Business type") or "","business_description":s.get("business_description") or fallback.get("Business description") or "","working_hours":s.get("working_hours") or fallback.get("Working hours") or "","reply_language":s.get("reply_language") or fallback.get("Reply language") or "auto","business_information":s.get("business_information") or (info.content if info else ""),"website":s.get("website") or (web.content.removeprefix("Official website: ") if web else ""),"booking_system":s.get("booking_system") or _int_val(db,company_id,"booking") or "","order_system":s.get("order_system") or _int_val(db,company_id,"orders") or "","other_system":s.get("other_system") or _int_val(db,company_id,"custom") or "","monthly_usage_limit":s.get("monthly_usage_limit"),"instructions":s.get("instructions") or ""}
 finally:db.close()
@router.put("/companies/{company_id}/{agent_id}/settings")
def update_settings(company_id:int,agent_id:int,data:AIEmployeeUpdate,current_admin:User=Depends(require_xvond_admin)):
 db=SessionLocal()
 try:
  company=db.query(Company).filter(Company.id==company_id).first();a=db.query(AIAgent).filter(AIAgent.id==agent_id,AIAgent.company_id==company_id).first();ch=db.query(AgentChannel).filter(AgentChannel.agent_id==agent_id,AgentChannel.company_id==company_id).first()
  if not company or not a or not ch:raise HTTPException(404,"AI employee not found")
  a.name=_clean(data.name) or a.name;a.system_prompt=_employee_prompt(company.name,data);_upsert_doc(db,company_id,agent_id,"Business Profile","business_profile",_profile(company,data));_upsert_doc(db,company_id,agent_id,"Business Information","text",_clean(data.business_information));_upsert_doc(db,company_id,agent_id,"Business Website","website_reference",f"Official website: {data.website.strip()}" if _clean(data.website) else None)
  for t,n,v in (("booking","Booking System",_clean(data.booking_system)),("orders","Orders / Store System",_clean(data.order_system)),("custom","Other Connected System",_clean(data.other_system))):_sync_int(db,company_id,t,n,v)
  cfg=dict(ch.config or {});cfg["employee_setup"]=_setup(company,data);ch.config=cfg;db.commit();return {"status":"updated"}
 except HTTPException:db.rollback();raise
 except Exception:db.rollback();raise
 finally:db.close()
def _delete_direct_agent_fk_rows(db,agent_id:int):
 rows=db.execute(text("""SELECT DISTINCT tc.table_name,kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name AND tc.constraint_schema=kcu.constraint_schema JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name AND ccu.constraint_schema=tc.constraint_schema WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public' AND ccu.table_schema='public' AND ccu.table_name='ai_agents' AND ccu.column_name='id'""")).all()
 for table_name,column_name in rows:
  if table_name!='ai_agents':db.execute(text(f'DELETE FROM "{table_name}" WHERE "{column_name}"=:agent_id'),{"agent_id":agent_id})
@router.delete("/companies/{company_id}/{agent_id}")
def delete_ai_employee(company_id:int,agent_id:int,current_admin:User=Depends(require_xvond_admin)):
 db=SessionLocal()
 try:
  a=db.query(AIAgent).filter(AIAgent.id==agent_id,AIAgent.company_id==company_id).first()
  if not a:raise HTTPException(404,"AI employee not found")
  ch=db.query(AgentChannel).filter(AgentChannel.agent_id==agent_id,AgentChannel.company_id==company_id).first()
  if ch and ch.enabled:raise HTTPException(409,"Disconnect/deactivate the live channel before permanently deleting this AI employee")
  ids=[x[0] for x in db.query(AIConversation.id).filter(AIConversation.agent_id==agent_id).all()]
  if ids:db.query(AIMessage).filter(AIMessage.conversation_id.in_(ids)).delete(synchronize_session=False)
  links=db.query(AgentKnowledge).filter(AgentKnowledge.agent_id==agent_id).all();dids=[x.document_id for x in links]
  _delete_direct_agent_fk_rows(db,agent_id)
  for did in dids:
   if not db.query(AgentKnowledge).filter(AgentKnowledge.document_id==did).first():db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id==did).delete(synchronize_session=False);db.query(KnowledgeDocument).filter(KnowledgeDocument.id==did,KnowledgeDocument.company_id==company_id).delete(synchronize_session=False)
  db.execute(text("DELETE FROM ai_agents WHERE id=:agent_id AND company_id=:company_id"),{"agent_id":agent_id,"company_id":company_id});db.commit();return {"status":"deleted"}
 except HTTPException:db.rollback();raise
 except Exception:db.rollback();raise
 finally:db.close()
