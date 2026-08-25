from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.tools.approval import tool_approval_service
from backend.app.modules.tools.executor import tool_executor


router = APIRouter(
    prefix="/admin/tool-execution",
    tags=["Xvond Admin - Tool Execution"],
)


class ToolExecuteInput(BaseModel):
    arguments: dict = Field(default_factory=dict)
    conversation_id: int | None = None


class ApprovalDecisionInput(BaseModel):
    approved: bool


@router.post("/companies/{company_id}/agents/{agent_id}/tools/{tool_name}")
def execute_agent_tool(
    company_id: int,
    agent_id: int,
    tool_name: str,
    data: ToolExecuteInput,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        result = tool_executor.execute(
            db=db,
            company_id=company_id,
            agent_id=agent_id,
            conversation_id=data.conversation_id,
            tool_name=tool_name,
            arguments=data.arguments,
            approval_granted=True,
        )
        if not result.get("success"):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=result.get("error") or "Tool execution failed",
            )
        db.commit()
        return {
            "success": True,
            "data": result.get("data"),
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/approvals/{approval_id}/decision")
def decide_tool_approval(
    approval_id: int,
    data: ApprovalDecisionInput,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        item = tool_approval_service.decide(
            db=db,
            approval_id=approval_id,
            approved=data.approved,
            user_id=current_admin.id,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Tool approval not found")
        db.commit()
        return {
            "id": item.id,
            "status": item.status,
            "approved": data.approved,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
