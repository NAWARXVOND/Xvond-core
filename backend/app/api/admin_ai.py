from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel

from backend.app.core.ai.engine import ai_engine
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User

from backend.app.modules.ai_agent.models import (
    AIAgent,
)


router = APIRouter(
    prefix="/admin",
    tags=["Xvond Admin - AI Agents"],
)


class AIAgentCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str
    provider: str = "mock"
    model: str = "test-model"


class AIAgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    provider: str | None = None
    model: str | None = None


def get_company(
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


def require_ai_module(
    db,
    company_id: int,
):
    item = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id
            == company_id,
            CompanyModule.module_name
            == "ai_agent",
            CompanyModule.enabled.is_(True),
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "AI Agent module is not enabled "
                "for this company"
            ),
        )


@router.get("/ai/providers")
def providers(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    return {
        "providers": ai_engine.list_providers(),
    }


@router.post(
    "/companies/{company_id}/agents"
)
def create_agent(
    company_id: int,
    data: AIAgentCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        require_ai_module(
            db,
            company_id,
        )

        if (
            data.provider
            not in ai_engine.list_providers()
        ):
            raise HTTPException(
                status_code=400,
                detail="AI provider is not configured",
            )

        agent = AIAgent(
            company_id=company_id,
            name=data.name,
            description=data.description,
            system_prompt=data.system_prompt,
            provider=data.provider,
            model=data.model,
            enabled=True,
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        return {
            "id": agent.id,
            "company_id": agent.company_id,
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model,
            "enabled": agent.enabled,
            "status": "created",
        }

    finally:
        db.close()


@router.get(
    "/companies/{company_id}/agents"
)
def list_company_agents(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        agents = (
            db.query(AIAgent)
            .filter(
                AIAgent.company_id
                == company_id
            )
            .order_by(
                AIAgent.id.asc()
            )
            .all()
        )

        return {
            "company_id": company_id,
            "agents": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "description": agent.description,
                    "provider": agent.provider,
                    "model": agent.model,
                    "enabled": agent.enabled,
                }
                for agent in agents
            ],
        }

    finally:
        db.close()


@router.get(
    "/companies/{company_id}/agents/{agent_id}"
)
def get_agent_detail(
    company_id: int,
    agent_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        return {
            "id": agent.id,
            "company_id": agent.company_id,
            "name": agent.name,
            "description": agent.description,
            "system_prompt": agent.system_prompt,
            "provider": agent.provider,
            "model": agent.model,
            "enabled": agent.enabled,
        }
    finally:
        db.close()


@router.put(
    "/companies/{company_id}/agents/{agent_id}"
)
def update_agent(
    company_id: int,
    agent_id: int,
    data: AIAgentUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        if data.provider is not None:
            if (
                data.provider
                not in ai_engine.list_providers()
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "AI provider is not configured"
                    ),
                )

            agent.provider = data.provider

        if data.name is not None:
            agent.name = data.name

        if data.description is not None:
            agent.description = data.description

        if data.system_prompt is not None:
            agent.system_prompt = (
                data.system_prompt
            )

        if data.model is not None:
            agent.model = data.model

        db.commit()
        db.refresh(agent)

        return {
            "id": agent.id,
            "company_id": agent.company_id,
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model,
            "enabled": agent.enabled,
            "status": "updated",
        }

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/agents/{agent_id}/enable"
)
def enable_agent(
    company_id: int,
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
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        agent.enabled = True

        db.commit()

        return {
            "id": agent.id,
            "enabled": True,
            "status": "enabled",
        }

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/agents/{agent_id}/disable"
)
def disable_agent(
    company_id: int,
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
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        agent.enabled = False

        db.commit()

        return {
            "id": agent.id,
            "enabled": False,
            "status": "disabled",
        }

    finally:
        db.close()

# ============================================================
# Xvond Admin - Test Agent
# ============================================================

from backend.app.core.agent_runtime import agent_runtime


class AdminTestChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


@router.post(
    "/companies/{company_id}/agents/{agent_id}/test-chat"
)
def test_agent_chat(
    company_id: int,
    agent_id: int,
    data: AdminTestChatRequest,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        require_ai_module(
            db,
            company_id,
        )

        return agent_runtime.chat(
            db=db,
            company_id=company_id,
            agent_id=agent_id,
            message=data.message,
            conversation_id=(
                data.conversation_id
            ),
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        )

    finally:
        db.close()
