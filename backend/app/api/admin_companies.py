from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User

router = APIRouter(prefix="/admin/companies", tags=["Xvond Admin - Companies"])


class CompanyStatusUpdate(BaseModel):
    active: bool


@router.patch("/{company_id}/status")
def update_company_status(
    company_id: int,
    payload: CompanyStatusUpdate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        company.active = payload.active
        db.commit()
        return {"status": "updated", "company_id": company_id, "active": company.active}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _table_exists(db, table_name: str) -> bool:
    return bool(
        db.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": f"public.{table_name}"},
        ).scalar()
    )


def _columns(db, table_name: str) -> set[str]:
    rows = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:table_name"
        ),
        {"table_name": table_name},
    ).all()
    return {row[0] for row in rows}


def _delete_where(db, table_name: str, where_sql: str, params: dict):
    if _table_exists(db, table_name):
        db.execute(text(f'DELETE FROM "{table_name}" WHERE {where_sql}'), params)


def _cleanup_agent_dependents(db, company_id: int):
    """Delete every row that directly/indirectly references this company's AI agents.

    This intentionally includes legacy tables such as agent_configs so old development
    companies can be removed safely after schema evolution.
    """
    agent_ids = [
        row[0]
        for row in db.execute(
            text("SELECT id FROM ai_agents WHERE company_id=:company_id"),
            {"company_id": company_id},
        ).all()
    ] if _table_exists(db, "ai_agents") else []
    if not agent_ids:
        return

    # Discover all public tables that currently have an FK pointing directly to ai_agents.
    # This prevents future/legacy agent child tables from breaking company deletion.
    fk_rows = db.execute(
        text("""
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
        """)
    ).all()

    # Conversations have messages beneath them, so clear message children first.
    if _table_exists(db, "ai_conversations") and _table_exists(db, "ai_messages"):
        db.execute(
            text("DELETE FROM ai_messages WHERE conversation_id IN "
                 "(SELECT id FROM ai_conversations WHERE agent_id = ANY(:agent_ids))"),
            {"agent_ids": agent_ids},
        )

    # Knowledge links can own generated documents/chunks. Save candidate document ids first.
    knowledge_doc_ids = []
    if _table_exists(db, "agent_knowledge"):
        cols = _columns(db, "agent_knowledge")
        if "agent_id" in cols and "document_id" in cols:
            knowledge_doc_ids = [
                row[0] for row in db.execute(
                    text("SELECT DISTINCT document_id FROM agent_knowledge WHERE agent_id = ANY(:agent_ids)"),
                    {"agent_ids": agent_ids},
                ).all()
            ]

    # Delete every direct AI-agent FK child, including agent_configs.
    for table_name, column_name in fk_rows:
        if table_name == "ai_agents":
            continue
        db.execute(
            text(f'DELETE FROM "{table_name}" WHERE "{column_name}" = ANY(:agent_ids)'),
            {"agent_ids": agent_ids},
        )

    # Remove employee-owned knowledge documents only when no other agent still references them.
    for document_id in knowledge_doc_ids:
        still_used = False
        if _table_exists(db, "agent_knowledge"):
            still_used = bool(db.execute(
                text("SELECT 1 FROM agent_knowledge WHERE document_id=:document_id LIMIT 1"),
                {"document_id": document_id},
            ).first())
        if not still_used:
            _delete_where(db, "knowledge_chunks", "document_id=:document_id", {"document_id": document_id})
            _delete_where(db, "knowledge_documents", "id=:document_id AND company_id=:company_id", {"document_id": document_id, "company_id": company_id})

    db.execute(text("DELETE FROM ai_agents WHERE company_id=:company_id"), {"company_id": company_id})


def _cleanup_company_tables(db, company_id: int):
    """Delete direct company-owned rows after agents are gone.

    Tables are discovered from the live PostgreSQL schema, so old/new module tables with a
    company_id column are included without hard-coding every Xvond module forever.
    """
    rows = db.execute(
        text("""
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema='public' AND column_name='company_id'
            ORDER BY table_name
        """)
    ).all()
    skip = {"companies", "ai_agents"}
    # Users may be company-scoped; deleting a company is intended to remove that tenant's users too.
    for (table_name,) in rows:
        if table_name in skip:
            continue
        db.execute(
            text(f'DELETE FROM "{table_name}" WHERE company_id=:company_id'),
            {"company_id": company_id},
        )


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        _cleanup_agent_dependents(db, company_id)
        _cleanup_company_tables(db, company_id)
        db.delete(company)
        db.commit()
        return {"status": "deleted", "company_id": company_id}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
