from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIConversation
from backend.app.modules.channels.handoff import activate_human_handoff, human_handoff_active, resume_ai
from backend.app.modules.channels.whatsapp_models import WhatsAppSession

router = APIRouter(prefix="/admin/handoff", tags=["Xvond Admin - Human Handoff"])


def _session_for_conversation(db, company_id: int, conversation_id: int) -> WhatsAppSession:
    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.company_id == company_id,
        )
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session = (
        db.query(WhatsAppSession)
        .filter(
            WhatsAppSession.company_id == company_id,
            WhatsAppSession.conversation_id == conversation_id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="WhatsApp session not found for this conversation")
    return session


@router.get("/companies/{company_id}/sessions")
def list_handoff_sessions(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        sessions = (
            db.query(WhatsAppSession)
            .filter(WhatsAppSession.company_id == company_id)
            .order_by(WhatsAppSession.updated_at.desc())
            .limit(500)
            .all()
        )
        result = []
        for session in sessions:
            active = human_handoff_active(session)
            result.append({
                "id": session.id,
                "conversation_id": session.conversation_id,
                "agent_id": session.agent_id,
                "wa_id": session.wa_id,
                "mode": "human" if active else "ai",
                "handoff_reason": session.handoff_reason,
                "human_takeover_until": session.human_takeover_until,
                "last_human_message_at": session.last_human_message_at,
                "updated_at": session.updated_at,
            })
        db.commit()
        return {"company_id": company_id, "sessions": result}
    finally:
        db.close()


@router.post("/companies/{company_id}/conversations/{conversation_id}/take-over")
def take_over(company_id: int, conversation_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        session = _session_for_conversation(db, company_id, conversation_id)
        activate_human_handoff(session, reason="admin_takeover", human_message=True)
        db.commit()
        return {
            "status": "human_active",
            "company_id": company_id,
            "conversation_id": conversation_id,
            "ai_paused": True,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/companies/{company_id}/conversations/{conversation_id}/return-ai")
def return_to_ai(company_id: int, conversation_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        session = _session_for_conversation(db, company_id, conversation_id)
        resume_ai(session)
        db.commit()
        return {
            "status": "ai_active",
            "company_id": company_id,
            "conversation_id": conversation_id,
            "ai_paused": False,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
