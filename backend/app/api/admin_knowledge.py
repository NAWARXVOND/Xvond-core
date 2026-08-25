from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service

router = APIRouter(prefix="/admin/knowledge", tags=["Xvond Admin - Knowledge Diagnostics"])


def _company(db, company_id: int):
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/companies/{company_id}/reindex")
def reindex_company_knowledge(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    """Diagnostic/maintenance endpoint only.

    Knowledge creation, editing, assignment and deletion intentionally live only
    in the AI Employee Knowledge API so protected company knowledge cannot be
    bypassed through a second admin surface.
    """
    db = SessionLocal()
    try:
        _company(db, company_id)
        documents = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.company_id == company_id
        ).all()
        total_chunks = 0
        for document in documents:
            total_chunks += knowledge_service.rebuild_document_index(db, document)
        db.commit()
        return {
            "company_id": company_id,
            "documents": len(documents),
            "chunks": total_chunks,
            "status": "reindexed",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/companies/{company_id}/status")
def company_knowledge_status(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        _company(db, company_id)
        documents = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.company_id == company_id
        ).count()
        enabled_documents = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.company_id == company_id,
            KnowledgeDocument.enabled.is_(True),
        ).count()
        chunks = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.company_id == company_id
        ).count()
        return {
            "company_id": company_id,
            "documents": documents,
            "enabled_documents": enabled_documents,
            "chunks": chunks,
        }
    finally:
        db.close()


@router.get("/agents/{agent_id}/context-preview")
def preview_agent_context(
    agent_id: int,
    q: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if agent is None:
            raise HTTPException(status_code=404, detail="AI Agent not found")
        knowledge_service.backfill_company_index(db, agent.company_id)
        matches = knowledge_service.search_agent_knowledge(
            db=db,
            company_id=agent.company_id,
            agent_id=agent.id,
            query=q,
        )
        db.commit()
        return {
            "agent_id": agent.id,
            "query": q,
            "matches": [
                {
                    "document_id": item.document_id,
                    "title": item.title,
                    "chunk_index": item.chunk_index,
                    "score": item.score,
                    "content": item.content,
                }
                for item in matches
            ],
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
