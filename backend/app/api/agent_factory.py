from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.ai_agent.factory import agent_factory
from backend.app.modules.ai_agent.factory_models import (
    AgentConfig,
    AgentTemplate,
)
from backend.app.modules.ai_agent.models import AIAgent


router = APIRouter(
    prefix="/admin/agent-factory",
    tags=["Xvond Admin - Agent Factory"],
)


class TemplateCreate(BaseModel):
    name: str
    category: str
    description: str | None = None
    default_system_prompt: str
    default_provider: str = "mock"
    default_model: str = "test-model"
    default_config: dict = Field(
        default_factory=dict
    )


class CustomAgentCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str

    provider: str = "mock"
    model: str = "test-model"

    agent_type: str = "custom"

    settings: dict = Field(
        default_factory=dict
    )

    capabilities: dict = Field(
        default_factory=dict
    )

    customer_controls: dict = Field(
        default_factory=lambda: {
            "can_enable_disable": True,
            "can_view_conversations": True,
            "can_view_usage": True,
            "can_edit_prompt": False,
            "can_change_provider": False,
            "can_change_model": False,
        }
    )


class TemplateAgentCreate(BaseModel):
    template_id: int

    name: str | None = None
    system_prompt: str | None = None

    provider: str | None = None
    model: str | None = None

    settings: dict = Field(
        default_factory=dict
    )


def require_company(
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


@router.post("/templates")
def create_template(
    data: TemplateCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        existing = (
            db.query(AgentTemplate)
            .filter(
                AgentTemplate.name
                == data.name
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=400,
                detail="Template already exists",
            )

        template = AgentTemplate(
            name=data.name,
            category=data.category,
            description=data.description,
            default_system_prompt=(
                data.default_system_prompt
            ),
            default_provider=(
                data.default_provider
            ),
            default_model=(
                data.default_model
            ),
            default_config=(
                data.default_config
            ),
            enabled=True,
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        return {
            "id": template.id,
            "name": template.name,
            "category": template.category,
            "enabled": template.enabled,
            "status": "created",
        }

    finally:
        db.close()


@router.get("/templates")
def list_templates(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        templates = (
            db.query(AgentTemplate)
            .order_by(
                AgentTemplate.id.asc()
            )
            .all()
        )

        return {
            "templates": [
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "description": item.description,
                    "provider": item.default_provider,
                    "model": item.default_model,
                    "enabled": item.enabled,
                }
                for item in templates
            ]
        }

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/custom-agent"
)
def create_custom_agent(
    company_id: int,
    data: CustomAgentCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        require_company(
            db,
            company_id,
        )

        try:
            agent = (
                agent_factory.create_custom_agent(
                    db=db,
                    company_id=company_id,
                    name=data.name,
                    description=data.description,
                    system_prompt=data.system_prompt,
                    provider=data.provider,
                    model=data.model,
                    agent_type=data.agent_type,
                    settings=data.settings,
                    capabilities=data.capabilities,
                    customer_controls=(
                        data.customer_controls
                    ),
                )
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

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

    except HTTPException:
        db.rollback()
        raise

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/from-template"
)
def create_agent_from_template(
    company_id: int,
    data: TemplateAgentCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        require_company(
            db,
            company_id,
        )

        template = (
            db.query(AgentTemplate)
            .filter(
                AgentTemplate.id
                == data.template_id,
                AgentTemplate.enabled.is_(
                    True
                ),
            )
            .first()
        )

        if template is None:
            raise HTTPException(
                status_code=404,
                detail="Agent template not found",
            )

        try:
            agent = (
                agent_factory.create_from_template(
                    db=db,
                    company_id=company_id,
                    template=template,
                    name=data.name,
                    system_prompt=(
                        data.system_prompt
                    ),
                    provider=data.provider,
                    model=data.model,
                    settings=data.settings,
                )
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

        db.commit()
        db.refresh(agent)

        return {
            "id": agent.id,
            "company_id": agent.company_id,
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model,
            "template_id": template.id,
            "status": "created",
        }

    except HTTPException:
        db.rollback()
        raise

    finally:
        db.close()


@router.get(
    "/companies/{company_id}/agents/{agent_id}"
)
def agent_factory_info(
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
                AIAgent.company_id
                == company_id,
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        config = (
            db.query(AgentConfig)
            .filter(
                AgentConfig.agent_id
                == agent.id
            )
            .first()
        )

        return {
            "agent": {
                "id": agent.id,
                "company_id": agent.company_id,
                "name": agent.name,
                "description": agent.description,
                "system_prompt": agent.system_prompt,
                "provider": agent.provider,
                "model": agent.model,
                "enabled": agent.enabled,
            },
            "config": None
            if config is None
            else {
                "agent_type": (
                    config.agent_type
                ),
                "settings": (
                    config.settings
                ),
                "capabilities": (
                    config.capabilities
                ),
                "customer_controls": (
                    config.customer_controls
                ),
            },
        }

    finally:
        db.close()
