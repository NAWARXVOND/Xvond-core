from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeChunk, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service

router = APIRouter(prefix="/admin/ai-employees", tags=["Xvond Admin - AI Employee Knowledge"])

ALLOWED_TYPES = {
    "general",
    "services_prices",
    "menu",
    "products",
    "faq",
    "policies",
    "branches",
    "hours",
    "delivery_payment",
    "booking_rules",
    "order_rules",
    "custom",
}

PROTECTED_TITLES = {"Business Profile", "Business Information", "Business Website"}

class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    category: str = "custom"
    content: str = Field(min_length=2, max_length=200000)

class KnowledgeUpdate(KnowledgeCreate):
    enabled: bool = True

def _agent(db, company_id: int, agent_id: int):
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.company_id == company_id).first()
    if agent is None:
        raise HTTPException(404, "AI employee not found")
    return agent

def _category(value: str) -> str:
    value = (value or "custom").strip().lower()
    if value not in ALLOWED_TYPES:
        raise HTTPException(400, "Unsupported knowledge category")
    return value

def _owned_document(db, company_id: int, agent_id: int, document_id: int):
    row = (
        db.query(KnowledgeDocument)
        .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.company_id == company_id,
            AgentKnowledge.agent_id == agent_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(404, "Knowledge item not found")
    return row

@router.get("/companies/{company_id}/{agent_id}/knowledge")
def list_employee_knowledge(company_id: int, agent_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        _agent(db, company_id, agent_id)
        rows = (
            db.query(KnowledgeDocument, AgentKnowledge)
            .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
            .filter(KnowledgeDocument.company_id == company_id, AgentKnowledge.agent_id == agent_id)
            .order_by(KnowledgeDocument.id.asc())
            .all()
        )
        return {
            "items": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "category": doc.source_type,
                    "enabled": bool(doc.enabled and link.enabled),
                    "characters": len(doc.content or ""),
                    "protected": doc.title in PROTECTED_TITLES,
                    "created_at": doc.created_at,
                    "preview": (doc.content or "")[:280],
                }
                for doc, link in rows
            ]
        }
    finally:
        db.close()

@router.get("/companies/{company_id}/{agent_id}/knowledge/{document_id}")
def get_employee_knowledge(company_id: int, agent_id: int, document_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        _agent(db, company_id, agent_id)
        doc = _owned_document(db, company_id, agent_id, document_id)
        return {"id": doc.id, "title": doc.title, "category": doc.source_type, "content": doc.content, "enabled": doc.enabled, "protected": doc.title in PROTECTED_TITLES}
    finally:
        db.close()

@router.post("/companies/{company_id}/{agent_id}/knowledge")
def create_employee_knowledge(company_id: int, agent_id: int, payload: KnowledgeCreate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        _agent(db, company_id, agent_id)
        title = payload.title.strip()
        category = _category(payload.category)
        content = payload.content.strip()
        existing = (
            db.query(KnowledgeDocument)
            .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
            .filter(KnowledgeDocument.company_id == company_id, AgentKnowledge.agent_id == agent_id, KnowledgeDocument.title == title)
            .first()
        )
        if existing:
            raise HTTPException(409, "A knowledge item with this title already exists")
        doc = KnowledgeDocument(company_id=company_id, title=title, source_type=category, content=content, enabled=True)
        db.add(doc); db.flush(); knowledge_service.rebuild_document_index(db, doc)
        db.add(AgentKnowledge(agent_id=agent_id, document_id=doc.id, enabled=True)); db.commit(); db.refresh(doc)
        return {"status": "created", "id": doc.id}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

@router.put("/companies/{company_id}/{agent_id}/knowledge/{document_id}")
def update_employee_knowledge(company_id: int, agent_id: int, document_id: int, payload: KnowledgeUpdate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        _agent(db, company_id, agent_id)
        doc = _owned_document(db, company_id, agent_id, document_id)
        if doc.title in PROTECTED_TITLES:
            raise HTTPException(409, "Edit protected business setup fields from AI Employee settings")
        doc.title = payload.title.strip(); doc.source_type = _category(payload.category); doc.content = payload.content.strip(); doc.enabled = payload.enabled
        link = db.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id, AgentKnowledge.document_id == document_id).first()
        if link: link.enabled = payload.enabled
        knowledge_service.rebuild_document_index(db, doc); db.commit(); return {"status": "updated"}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

@router.patch("/companies/{company_id}/{agent_id}/knowledge/{document_id}/toggle")
def toggle_employee_knowledge(company_id: int, agent_id: int, document_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        _agent(db, company_id, agent_id); doc = _owned_document(db, company_id, agent_id, document_id)
        link = db.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id, AgentKnowledge.document_id == document_id).first()
        new_value = not bool(doc.enabled and link and link.enabled); doc.enabled = new_value
        if link: link.enabled = new_value
        db.commit(); return {"status": "updated", "enabled": new_value}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

@router.delete("/companies/{company_id}/{agent_id}/knowledge/{document_id}")
def delete_employee_knowledge(company_id: int, agent_id: int, document_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        _agent(db, company_id, agent_id); doc = _owned_document(db, company_id, agent_id, document_id)
        if doc.title in PROTECTED_TITLES:
            raise HTTPException(409, "Protected business setup knowledge cannot be deleted here")
        db.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id, AgentKnowledge.document_id == document_id).delete(synchronize_session=False)
        remaining = db.query(AgentKnowledge).filter(AgentKnowledge.document_id == document_id).first()
        if remaining is None:
            db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).delete(synchronize_session=False)
            db.delete(doc)
        db.commit(); return {"status": "deleted"}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
