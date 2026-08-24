from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import get_current_user

from backend.app.models.user import User

from backend.app.modules.ai_agent.factory_models import AgentConfig
from backend.app.modules.ai_agent.models import AIAgent


router = APIRouter(
    prefix="/customer/agents",
    tags=["Customer Agent Controls"],
)


class AgentCustomerUpdate(BaseModel):
    enabled: bool | None = None


def get_customer_agent(
    db,
    user: User,
    agent_id: int,
):
    if user.company_id is None:
        raise HTTPException(
            status_code=403,
            detail="Customer company required",
        )

    agent = (
        db.query(AIAgent)
        .filter(
            AIAgent.id == agent_id,
            AIAgent.company_id == user.company_id,
        )
        .first()
    )

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="AI Agent not found",
        )

    return agent


@router.get("/{agent_id}")
def agent_details(
    agent_id: int,
    current_user: User = Depends(get_current_user),
):
    db = SessionLocal()

    try:
        agent = get_customer_agent(
            db,
            current_user,
            agent_id,
        )

        config = (
            db.query(AgentConfig)
            .filter(
                AgentConfig.agent_id == agent.id
            )
            .first()
        )

        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "provider": agent.provider,
            "model": agent.model,
            "enabled": agent.enabled,
            "controls": (
                config.customer_controls
                if config
                else {}
            ),
        }

    finally:
        db.close()


@router.patch("/{agent_id}")
def update_agent(
    agent_id: int,
    data: AgentCustomerUpdate,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {
        "owner",
        "admin",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Company owner or admin required"
            ),
        )

    db = SessionLocal()

    try:
        agent = get_customer_agent(
            db,
            current_user,
            agent_id,
        )

        config = (
            db.query(AgentConfig)
            .filter(
                AgentConfig.agent_id == agent.id
            )
            .first()
        )

        controls = (
            config.customer_controls
            if config
            else {}
        )

        if data.enabled is not None:
            if not controls.get(
                "can_enable_disable",
                False,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Customer cannot enable "
                        "or disable this agent"
                    ),
                )

            agent.enabled = data.enabled

        db.commit()
        db.refresh(agent)

        return {
            "id": agent.id,
            "enabled": agent.enabled,
            "status": "updated",
        }

    finally:
        db.close()
