from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.tools.executor import tool_executor


router = APIRouter(
    prefix="/admin/tool-execution",
    tags=["Xvond Admin - Tool Execution"],
)


class ToolExecuteInput(BaseModel):
    arguments: dict = Field(default_factory=dict)
    conversation_id: int | None = None


@router.post("/companies/{company_id}/agents/{agent_id}/tools/{tool_name}")
def execute_agent_tool(
    company_id: int,
    agent_id: int,
    tool_name: str,
    data: ToolExecuteInput,
    current_admin: User = Depends(require_xvond_admin),
):
    """Internal Xvond-admin execution path for a configured agent tool.

    The retired generic approval workflow is intentionally not exposed here.
    Customer-facing business actions use the canonical ActionRequest flow and
    its explicit confirmation/execution lifecycle instead.
    """
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
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
