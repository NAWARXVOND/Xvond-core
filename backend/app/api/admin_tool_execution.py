from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.tools.executor import tool_executor


router = APIRouter(
    prefix="/admin/tool-execution",
    tags=["Xvond Admin - Tool Execution"],
)


class ToolExecutionRequest(BaseModel):
    arguments: dict[str, Any] = {}


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
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result,
            )

        return result

    finally:
        db.close()

