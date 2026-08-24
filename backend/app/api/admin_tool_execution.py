from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.tools.executor import tool_executor
from backend.app.modules.tools.models import ToolApprovalRequest


router = APIRouter(
    prefix="/admin/tool-execution",
    tags=["Xvond Admin - Tool Execution"],
)


class ToolExecutionRequest(BaseModel):
    arguments: dict[str, Any] = {}


class ToolDecisionRequest(BaseModel):
    note: str | None = None


@router.get("/agents/{agent_id}/tools")
def agent_tools(
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
                detail="Agent not found",
            )

        return {
            "agent_id": agent.id,
            "tools": tool_executor.get_agent_tools(
                db=db,
                agent_id=agent.id,
            ),
        }

    finally:
        db.close()


@router.post(
    "/agents/{agent_id}/tools/{tool_name}"
)
def execute_agent_tool(
    agent_id: int,
    tool_name: str,
    data: ToolExecutionRequest,
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
                detail="Agent not found",
            )

        result = tool_executor.execute(
            db=db,
            company_id=agent.company_id,
            agent_id=agent.id,
            tool_name=tool_name,
            arguments=data.arguments,
            approval_granted=True,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result,
            )

        return result

    finally:
        db.close()



@router.get("/approvals")
def list_pending_approvals(
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        items = (
            db.query(ToolApprovalRequest)
            .filter(ToolApprovalRequest.status == "pending")
            .order_by(ToolApprovalRequest.id.asc())
            .all()
        )
        return {
            "approvals": [
                {
                    "id": item.id,
                    "company_id": item.company_id,
                    "agent_id": item.agent_id,
                    "conversation_id": item.conversation_id,
                    "tool_name": item.tool_name,
                    "arguments": item.arguments,
                    "status": item.status,
                    "created_at": item.created_at,
                }
                for item in items
            ]
        }
    finally:
        db.close()


@router.post("/approvals/{approval_id}/approve")
def approve_tool_execution(
    approval_id: int,
    data: ToolDecisionRequest,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        item = (
            db.query(ToolApprovalRequest)
            .filter(
                ToolApprovalRequest.id == approval_id,
                ToolApprovalRequest.status == "pending",
            )
            .first()
        )
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Pending approval request not found",
            )

        result = tool_executor.execute(
            db=db,
            company_id=item.company_id,
            agent_id=item.agent_id,
            tool_name=item.tool_name,
            arguments=item.arguments,
            conversation_id=item.conversation_id,
            approval_granted=True,
        )

        item.status = "executed" if result.get("success") else "failed"
        item.result = result
        item.decision_note = data.note
        item.decided_by = current_admin.id
        item.decided_at = datetime.utcnow()
        db.commit()

        return {
            "approval_id": item.id,
            "status": item.status,
            "result": result,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/approvals/{approval_id}/reject")
def reject_tool_execution(
    approval_id: int,
    data: ToolDecisionRequest,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        item = (
            db.query(ToolApprovalRequest)
            .filter(
                ToolApprovalRequest.id == approval_id,
                ToolApprovalRequest.status == "pending",
            )
            .first()
        )
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Pending approval request not found",
            )

        item.status = "rejected"
        item.decision_note = data.note
        item.decided_by = current_admin.id
        item.decided_at = datetime.utcnow()
        db.commit()

        return {
            "approval_id": item.id,
            "status": item.status,
        }
    finally:
        db.close()
