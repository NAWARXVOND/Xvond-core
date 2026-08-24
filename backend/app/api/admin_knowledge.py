from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.ai_agent.models import AIAgent

from backend.app.modules.knowledge.models import (
    AgentKnowledge,
    KnowledgeChunk,
    KnowledgeDocument,
)

from backend.app.modules.knowledge.service import (
    knowledge_service,
)


router = APIRouter(
    prefix="/admin/knowledge",
    tags=["Xvond Admin - Knowledge"],
)


class KnowledgeCreate(BaseModel):
    title: str
    source_type: str = "text"
    content: str


class KnowledgeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    enabled: bool | None = None


def get_company_or_404(
    db,
    company_id: int,
):

    company = (
        db.query(Company)
        .filter(
            Company.id == company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return company


def get_document_or_404(
    db,
    company_id: int,
    document_id: int,
):

    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id
            == document_id,
            KnowledgeDocument.company_id
            == company_id,
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Knowledge document not found",
        )

    return document


# ============================================================
# CREATE
# ============================================================

@router.post(
    "/companies/{company_id}/documents"
)
def create_document(
    company_id: int,
    data: KnowledgeCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        normalized_title = (
            data.title
            .strip()
        )

        normalized_content = (
            data.content
            .strip()
        )

        # --------------------------------------------
        # Prevent exact duplicate
        # --------------------------------------------

        existing = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id
                == company_id,
                KnowledgeDocument.title
                == normalized_title,
                KnowledgeDocument.content
                == normalized_content,
            )
            .first()
        )

        if existing is not None:

            return {
                "id": existing.id,
                "company_id": existing.company_id,
                "title": existing.title,
                "source_type": existing.source_type,
                "enabled": existing.enabled,
                "status": "already_exists",
            }

        document = KnowledgeDocument(
            company_id=company_id,
            title=normalized_title,
            source_type=data.source_type,
            content=normalized_content,
            enabled=True,
        )

        db.add(document)
        db.flush()

        knowledge_service.rebuild_document_index(
            db,
            document,
        )

        db.commit()

        db.refresh(document)

        return {
            "id": document.id,
            "company_id": document.company_id,
            "title": document.title,
            "source_type": document.source_type,
            "enabled": document.enabled,
            "status": "created",
        }

    finally:
        db.close()


# ============================================================
# LIST COMPANY DOCUMENTS
# ============================================================

@router.get(
    "/companies/{company_id}/documents"
)
def list_documents(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id
                == company_id
            )
            .order_by(
                KnowledgeDocument.id.asc()
            )
            .all()
        )

        return {
            "documents": [
                {
                    "id": item.id,
                    "title": item.title,
                    "source_type": item.source_type,
                    "content": item.content,
                    "enabled": item.enabled,
                    "created_at": item.created_at,
                }
                for item in documents
            ]
        }

    finally:
        db.close()


# ============================================================
# GET ONE DOCUMENT
# ============================================================

@router.get(
    "/companies/{company_id}/documents/{document_id}"
)
def get_document(
    company_id: int,
    document_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        document = get_document_or_404(
            db,
            company_id,
            document_id,
        )

        return {
            "id": document.id,
            "company_id": document.company_id,
            "title": document.title,
            "source_type": document.source_type,
            "content": document.content,
            "enabled": document.enabled,
            "created_at": document.created_at,
        }

    finally:
        db.close()


# ============================================================
# UPDATE DOCUMENT
# ============================================================

@router.patch(
    "/companies/{company_id}/documents/{document_id}"
)
def update_document(
    company_id: int,
    document_id: int,
    data: KnowledgeUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        document = get_document_or_404(
            db,
            company_id,
            document_id,
        )

        if data.title is not None:
            document.title = (
                data.title.strip()
            )

        if data.content is not None:
            document.content = (
                data.content.strip()
            )

        if data.enabled is not None:
            document.enabled = (
                data.enabled
            )

        if data.content is not None:
            knowledge_service.rebuild_document_index(
                db,
                document,
            )

        db.commit()

        db.refresh(document)

        return {
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "enabled": document.enabled,
            "status": "updated",
        }

    finally:
        db.close()


# ============================================================
# DELETE DOCUMENT
# ============================================================

@router.delete(
    "/companies/{company_id}/documents/{document_id}"
)
def delete_document(
    company_id: int,
    document_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        document = get_document_or_404(
            db,
            company_id,
            document_id,
        )

        (
            db.query(AgentKnowledge)
            .filter(
                AgentKnowledge.document_id
                == document.id
            )
            .delete(
                synchronize_session=False
            )
        )

        (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.document_id
                == document.id
            )
            .delete(
                synchronize_session=False
            )
        )

        db.delete(document)

        db.commit()

        return {
            "document_id": document_id,
            "status": "deleted",
        }

    finally:
        db.close()


# ============================================================
# CONNECT DOCUMENT TO AGENT
# ============================================================

@router.post(
    "/agents/{agent_id}/documents/{document_id}"
)
def connect_document_to_agent(
    agent_id: int,
    document_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        document = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.id
                == document_id,
                KnowledgeDocument.company_id
                == agent.company_id,
            )
            .first()
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Knowledge document not found",
            )

        existing = (
            db.query(AgentKnowledge)
            .filter(
                AgentKnowledge.agent_id
                == agent_id,
                AgentKnowledge.document_id
                == document_id,
            )
            .first()
        )

        if existing is not None:

            existing.enabled = True

            db.commit()

            return {
                "agent_id": agent_id,
                "document_id": document_id,
                "status": "already_connected",
            }

        link = AgentKnowledge(
            agent_id=agent_id,
            document_id=document_id,
            enabled=True,
        )

        db.add(link)

        db.commit()

        return {
            "agent_id": agent_id,
            "document_id": document_id,
            "status": "connected",
        }

    finally:
        db.close()


# ============================================================
# LIST AGENT KNOWLEDGE
# ============================================================

@router.get(
    "/agents/{agent_id}/documents"
)
def list_agent_documents(
    agent_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        rows = (
            db.query(
                KnowledgeDocument,
                AgentKnowledge,
            )
            .join(
                AgentKnowledge,
                AgentKnowledge.document_id
                == KnowledgeDocument.id,
            )
            .filter(
                AgentKnowledge.agent_id
                == agent_id
            )
            .order_by(
                KnowledgeDocument.id.asc()
            )
            .all()
        )

        return {
            "agent_id": agent_id,
            "documents": [
                {
                    "id": document.id,
                    "title": document.title,
                    "content": document.content,
                    "source_type": document.source_type,
                    "document_enabled": document.enabled,
                    "connected": link.enabled,
                }
                for document, link in rows
            ],
        }

    finally:
        db.close()


# ============================================================
# DISCONNECT FROM AGENT
# ============================================================

@router.delete(
    "/agents/{agent_id}/documents/{document_id}"
)
def disconnect_document(
    agent_id: int,
    document_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        link = (
            db.query(AgentKnowledge)
            .filter(
                AgentKnowledge.agent_id
                == agent_id,
                AgentKnowledge.document_id
                == document_id,
            )
            .first()
        )

        if link is None:
            raise HTTPException(
                status_code=404,
                detail="Knowledge connection not found",
            )

        db.delete(link)

        db.commit()

        return {
            "agent_id": agent_id,
            "document_id": document_id,
            "status": "disconnected",
        }

    finally:
        db.close()



# ============================================================
# REINDEX COMPANY KNOWLEDGE
# ============================================================

@router.post(
    "/companies/{company_id}/reindex"
)
def reindex_company_knowledge(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id
                == company_id
            )
            .all()
        )

        total_chunks = 0

        for document in documents:

            total_chunks += (
                knowledge_service
                .rebuild_document_index(
                    db,
                    document,
                )
            )

        db.commit()

        return {
            "company_id": company_id,
            "documents":
                len(documents),
            "chunks":
                total_chunks,
            "status":
                "reindexed",
        }

    finally:
        db.close()


# ============================================================
# KNOWLEDGE STATUS
# ============================================================

@router.get(
    "/companies/{company_id}/status"
)
def company_knowledge_status(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id
                == company_id
            )
            .count()
        )

        enabled_documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id
                == company_id,
                KnowledgeDocument.enabled
                .is_(True),
            )
            .count()
        )

        chunks = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.company_id
                == company_id
            )
            .count()
        )

        return {
            "company_id":
                company_id,
            "documents":
                documents,
            "enabled_documents":
                enabled_documents,
            "chunks":
                chunks,
        }

    finally:
        db.close()


# ============================================================
# PREVIEW AGENT RETRIEVAL
# ============================================================

@router.get(
    "/agents/{agent_id}/context-preview"
)
def preview_agent_context(
    agent_id: int,
    q: str,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id
                == agent_id
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        knowledge_service.backfill_company_index(
            db,
            agent.company_id,
        )

        matches = (
            knowledge_service
            .search_agent_knowledge(
                db=db,
                company_id=agent.company_id,
                agent_id=agent.id,
                query=q,
            )
        )

        db.commit()

        return {
            "agent_id":
                agent.id,
            "query":
                q,
            "matches": [
                {
                    "document_id":
                        item.document_id,
                    "title":
                        item.title,
                    "chunk_index":
                        item.chunk_index,
                    "score":
                        item.score,
                    "content":
                        item.content,
                }
                for item in matches
            ],
        }

    finally:
        db.close()
