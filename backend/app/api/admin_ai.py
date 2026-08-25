from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.ai.engine import ai_engine
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User

router = APIRouter(prefix="/admin", tags=["Xvond Admin - AI Diagnostics"])


class AdminTestChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


def _require_company(db, company_id: int):
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _require_ai_module(db, company_id: int):
    item = db.query(CompanyModule).filter(
        CompanyModule.company_id == company_id,
        CompanyModule.module_name == "ai_agent",
        CompanyModule.enabled.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=400, detail="AI Agent module is not enabled for this company")


@router.get("/ai/providers")
def providers(current_admin: User = Depends(require_xvond_admin)):
    return {"providers": ai_engine.list_providers()}


@router.post("/companies/{company_id}/agents/{agent_id}/test-chat")
def test_agent_chat(
    company_id: int,
    agent_id: int,
    data: AdminTestChatRequest,
    current_admin: User = Depends(require_xvond_admin),
):
    """Admin-only runtime test.

    AI employee creation/editing intentionally lives only in
    /admin/ai-employee-profile so there is one canonical mutation path.
    """
    db = SessionLocal()
    try:
        _require_company(db, company_id)
        _require_ai_module(db, company_id)
        return agent_runtime.chat(
            db=db,
            company_id=company_id,
            agent_id=agent_id,
            message=data.message,
            conversation_id=data.conversation_id,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        db.close()
