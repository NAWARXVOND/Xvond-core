from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeChunk, KnowledgeDocument
from backend.app.modules.providers.models import AIModelRecord, AIProviderRecord, CompanyAIProfile

router = APIRouter(prefix="/admin/ai-employees", tags=["Xvond Admin - AI Employees"])


def _ensure_module(db, company_id: int, name: str):
    """Canonical helper used by the AI Employee Profile API."""
    row = db.query(CompanyModule).filter(
        CompanyModule.company_id == company_id,
        CompanyModule.module_name == name,
    ).first()
    if row is None:
        row = CompanyModule(company_id=company_id, module_name=name, enabled=True)
        db.add(row)
    else:
        row.enabled = True
    return row


def _select_model(db, company_id: int):
    """Select the configured company default or the first enabled catalog model."""
    profile = db.query(CompanyAIProfile).filter(
        CompanyAIProfile.company_id == company_id
    ).first()
    if profile and profile.default_provider and profile.default_model:
        valid = (
            db.query(AIModelRecord)
            .join(AIProviderRecord, AIProviderRecord.name == AIModelRecord.provider_name)
            .filter(
                AIModelRecord.provider_name == profile.default_provider,
                AIModelRecord.model_name == profile.default_model,
                AIModelRecord.enabled.is_(True),
                AIProviderRecord.enabled.is_(True),
            )
            .first()
        )
        if valid is not None:
            return profile.default_provider, profile.default_model

    row = (
        db.query(AIModelRecord, AIProviderRecord)
        .join(AIProviderRecord, AIProviderRecord.name == AIModelRecord.provider_name)
        .filter(
            AIModelRecord.enabled.is_(True),
            AIProviderRecord.enabled.is_(True),
        )
        .order_by(AIProviderRecord.priority.asc(), AIModelRecord.id.asc())
        .first()
    )
    if not row:
        raise HTTPException(400, "No enabled AI provider/model is configured")
    model, provider = row
    return provider.name, model.model_name


def _delete_direct_agent_fk_rows(db, agent_id: int):
    """Delete rows that directly reference ai_agents before deleting the agent.

    The project has optional modules whose tables may not exist in every older
    installation. Discovering actual FK references keeps deletion compatible
    across upgraded databases while still relying on database metadata rather
    than guessed table names.
    """
    rows = db.execute(text("""
        SELECT DISTINCT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.constraint_schema = kcu.constraint_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.constraint_schema = tc.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_schema = 'public'
          AND ccu.table_name = 'ai_agents'
          AND ccu.column_name = 'id'
    """)).all()
    for table_name, column_name in rows:
        if table_name != "ai_agents":
            db.execute(
                text(f'DELETE FROM "{table_name}" WHERE "{column_name}"=:agent_id'),
                {"agent_id": agent_id},
            )


@router.delete("/companies/{company_id}/{agent_id}")
def delete_ai_employee(
    company_id: int,
    agent_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    """The only active route kept in this legacy module.

    Creation and editing are intentionally owned by /admin/ai-employee-profile.
    """
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(
            AIAgent.id == agent_id,
            AIAgent.company_id == company_id,
        ).first()
        if not agent:
            raise HTTPException(404, "AI employee not found")

        live_channel = db.query(AgentChannel).filter(
            AgentChannel.agent_id == agent_id,
            AgentChannel.company_id == company_id,
            AgentChannel.enabled.is_(True),
        ).first()
        if live_channel is not None:
            raise HTTPException(
                409,
                "Disconnect/deactivate all live channels before permanently deleting this AI employee",
            )

        conversation_ids = [
            row[0]
            for row in db.query(AIConversation.id).filter(
                AIConversation.agent_id == agent_id,
                AIConversation.company_id == company_id,
            ).all()
        ]
        if conversation_ids:
            db.query(AIMessage).filter(
                AIMessage.conversation_id.in_(conversation_ids)
            ).delete(synchronize_session=False)

        links = db.query(AgentKnowledge).filter(
            AgentKnowledge.agent_id == agent_id
        ).all()
        document_ids = [link.document_id for link in links]

        _delete_direct_agent_fk_rows(db, agent_id)

        # Remove documents that belonged only to this employee. Shared company
        # knowledge is preserved as long as another employee still references it.
        for document_id in document_ids:
            if not db.query(AgentKnowledge).filter(
                AgentKnowledge.document_id == document_id
            ).first():
                db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.document_id == document_id
                ).delete(synchronize_session=False)
                db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.company_id == company_id,
                ).delete(synchronize_session=False)

        db.execute(
            text("DELETE FROM ai_agents WHERE id=:agent_id AND company_id=:company_id"),
            {"agent_id": agent_id, "company_id": company_id},
        )
        db.commit()
        return {"status": "deleted"}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
