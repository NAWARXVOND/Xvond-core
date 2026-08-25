from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIConversation, AIMessage
from backend.app.modules.channels.handoff import activate_human_handoff, human_handoff_active, resume_ai
from backend.app.modules.channels.whatsapp_models import WhatsAppSession
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(prefix="/admin/handoff", tags=["Xvond Admin - Human Handoff"])
ACTIVE_STATUSES={"pending","in_progress"}

class HumanMessage(BaseModel):
    message:str=Field(min_length=1,max_length=12000)


def _conversation(db,company_id,conversation_id):
    row=db.query(AIConversation).filter(AIConversation.id==conversation_id,AIConversation.company_id==company_id).first()
    if row is None:raise HTTPException(404,"Conversation not found")
    return row

def _session(db,company_id,conversation_id):
    return db.query(WhatsAppSession).filter(WhatsAppSession.company_id==company_id,WhatsAppSession.conversation_id==conversation_id).first()

def _active_handoff(db,company_id,conversation_id):
    return db.query(HumanHandoff).filter(HumanHandoff.company_id==company_id,HumanHandoff.conversation_id==conversation_id,HumanHandoff.status.in_(ACTIVE_STATUSES)).order_by(HumanHandoff.id.desc()).first()

@router.get("/companies/{company_id}/sessions")
def list_handoff_sessions(company_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        conversations=db.query(AIConversation).filter(AIConversation.company_id==company_id).order_by(AIConversation.id.desc()).limit(500).all();result=[]
        for conversation in conversations:
            session=_session(db,company_id,conversation.id);handoff=_active_handoff(db,company_id,conversation.id);active=bool(handoff or (session and human_handoff_active(session)))
            last=db.query(AIMessage).filter(AIMessage.conversation_id==conversation.id).order_by(AIMessage.id.desc()).first()
            result.append({"id":session.id if session else None,"conversation_id":conversation.id,"agent_id":conversation.agent_id,"wa_id":session.wa_id if session else None,"channel":"whatsapp" if session else "website_or_other","mode":"human" if active else "ai","handoff_reason":handoff.reason if handoff else (session.handoff_reason if session else None),"last_message":last.content[:250] if last else None,"updated_at":session.updated_at if session else conversation.created_at})
        return {"company_id":company_id,"sessions":result}
    finally:db.close()

@router.post("/companies/{company_id}/conversations/{conversation_id}/take-over")
def take_over(company_id:int,conversation_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        conversation=_conversation(db,company_id,conversation_id);session=_session(db,company_id,conversation_id);handoff=_active_handoff(db,company_id,conversation_id)
        if handoff is None:
            handoff=HumanHandoff(company_id=company_id,agent_id=conversation.agent_id,conversation_id=conversation.id,reason="admin_takeover",priority="normal",department="customer_service",status="in_progress");db.add(handoff)
        else:handoff.status="in_progress"
        if session:activate_human_handoff(session,reason="admin_takeover",human_message=True)
        db.commit();return {"status":"human_active","company_id":company_id,"conversation_id":conversation_id,"ai_paused":True}
    except HTTPException:db.rollback();raise
    except Exception:db.rollback();raise
    finally:db.close()

@router.post("/companies/{company_id}/conversations/{conversation_id}/return-ai")
def return_to_ai(company_id:int,conversation_id:int,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        _conversation(db,company_id,conversation_id);session=_session(db,company_id,conversation_id)
        for handoff in db.query(HumanHandoff).filter(HumanHandoff.company_id==company_id,HumanHandoff.conversation_id==conversation_id,HumanHandoff.status.in_(ACTIVE_STATUSES)).all():handoff.status="completed"
        if session:resume_ai(session)
        db.commit();return {"status":"ai_active","company_id":company_id,"conversation_id":conversation_id,"ai_paused":False}
    except HTTPException:db.rollback();raise
    except Exception:db.rollback();raise
    finally:db.close()

@router.post("/companies/{company_id}/conversations/{conversation_id}/message")
def send_human_message(company_id:int,conversation_id:int,data:HumanMessage,current_admin:User=Depends(require_xvond_admin)):
    db=SessionLocal()
    try:
        conversation=_conversation(db,company_id,conversation_id);handoff=_active_handoff(db,company_id,conversation_id)
        if handoff is None:raise HTTPException(409,"Take over the conversation before sending a human reply")
        handoff.status="in_progress";message=AIMessage(conversation_id=conversation.id,role="human",content=data.message.strip());db.add(message);db.commit();db.refresh(message)
        return {"status":"sent","message":{"id":message.id,"role":"human","content":message.content}}
    except HTTPException:db.rollback();raise
    finally:db.close()
