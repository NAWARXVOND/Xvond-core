from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.factory import agent_factory
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.solutions.catalog import (
    AI_EMPLOYEE_CAPABILITIES,
    AI_EMPLOYEE_CHANNELS,
    PACKAGE_TIERS,
    SERVICE_CATALOG,
    public_catalog,
)
from backend.app.modules.solutions.models import CompanySolution
from backend.app.modules.tools.models import AgentToolAssignment


router = APIRouter(
    prefix="/admin/solutions",
    tags=["Xvond Admin - Solutions"],
)

ALLOWED_STATUSES = {
    "discovery",
    "planned",
    "setup",
    "testing",
    "active",
    "paused",
    "completed",
}

CAPABILITY_TO_TOOL = {
    "lead_capture": "lead",
    "booking": "booking",
    "orders": "order",
    "human_handoff": "human_handoff",
}


class SolutionCreate(BaseModel):
    service_code: str
    name: str
    package_tier: str = "business"
    status: str = "discovery"
    description: str | None = None
    configuration: dict = Field(default_factory=dict)


class SolutionStatusUpdate(BaseModel):
    status: str


class AIEmployeeCreate(BaseModel):
    name: str
    description: str | None = None
    package_tier: str = "business"
    provider: str
    model: str
    system_prompt: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


def require_company(db, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def validate_choice(value: str, choices: dict, label: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in choices:
        raise HTTPException(status_code=400, detail=f"Unsupported {label}: {value}")
    return normalized


def validate_many(values: list[str], choices: dict, label: str) -> list[str]:
    result = []
    for value in values:
        normalized = validate_choice(value, choices, label)
        if normalized not in result:
            result.append(normalized)
    return result


def ensure_company_module(db, company_id: int, module_name: str):
    item = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id == company_id,
            CompanyModule.module_name == module_name,
        )
        .first()
    )
    if item is None:
        item = CompanyModule(
            company_id=company_id,
            module_name=module_name,
            enabled=True,
            installed_at=datetime.utcnow(),
        )
        db.add(item)
    else:
        item.enabled = True
    return item


def serialize_solution(item: CompanySolution) -> dict:
    catalog_item = SERVICE_CATALOG.get(item.service_code, {})
    return {
        "id": item.id,
        "company_id": item.company_id,
        "service_code": item.service_code,
        "service_name": catalog_item.get("name", item.service_code),
        "name": item.name,
        "package_tier": item.package_tier,
        "status": item.status,
        "description": item.description,
        "capabilities": item.capabilities,
        "channels": item.channels,
        "configuration": item.configuration,
        "linked_agent_id": item.linked_agent_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/catalog")
def get_catalog(current_admin: User = Depends(require_xvond_admin)):
    return public_catalog()


@router.get("/companies/{company_id}")
def list_company_solutions(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        items = (
            db.query(CompanySolution)
            .filter(CompanySolution.company_id == company_id)
            .order_by(CompanySolution.id.desc())
            .all()
        )
        return {
            "company_id": company_id,
            "solutions": [serialize_solution(item) for item in items],
        }
    finally:
        db.close()


@router.post("/companies/{company_id}")
def create_solution(
    company_id: int,
    data: SolutionCreate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        service_code = validate_choice(
            data.service_code, SERVICE_CATALOG, "service"
        )
        package_tier = validate_choice(
            data.package_tier, PACKAGE_TIERS, "package"
        )
        status = validate_choice(data.status, ALLOWED_STATUSES, "status")
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Solution name is required")

        ensure_company_module(db, company_id, "solutions")
        item = CompanySolution(
            company_id=company_id,
            service_code=service_code,
            name=name,
            package_tier=package_tier,
            status=status,
            description=data.description,
            capabilities=[],
            channels=[],
            configuration=data.configuration,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return serialize_solution(item)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/companies/{company_id}/ai-employee")
def provision_ai_employee(
    company_id: int,
    data: AIEmployeeCreate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        package_tier = validate_choice(
            data.package_tier, PACKAGE_TIERS, "package"
        )
        capabilities = validate_many(
            data.capabilities, AI_EMPLOYEE_CAPABILITIES, "capability"
        )
        channels = validate_many(
            data.channels, AI_EMPLOYEE_CHANNELS, "channel"
        )
        if not capabilities:
            raise HTTPException(
                status_code=400,
                detail="Select at least one employee capability",
            )
        if not channels:
            raise HTTPException(
                status_code=400,
                detail="Select at least one delivery channel",
            )

        prompt = (data.system_prompt or "").strip() or (
            "You are a professional AI employee for this company. "
            "Use connected company knowledge and tools. Answer in the customer's "
            "language. Never invent prices, policies, availability, bookings, or "
            "orders. Use the configured tools for actions. Transfer to a human "
            "when requested or when a reliable answer is unavailable."
        )

        ensure_company_module(db, company_id, "solutions")
        ensure_company_module(db, company_id, "ai_agent")
        ensure_company_module(db, company_id, "channels")

        try:
            agent = agent_factory.create_custom_agent(
                db=db,
                company_id=company_id,
                name=data.name,
                description=data.description,
                system_prompt=prompt,
                provider=data.provider,
                model=data.model,
                agent_type="ai_employee",
                settings={
                    **data.settings,
                    "package_tier": package_tier,
                    "provisioned_by": "solutions",
                },
                capabilities={code: True for code in capabilities},
                customer_controls={
                    "can_enable_disable": True,
                    "can_view_conversations": True,
                    "can_view_usage": True,
                    "can_edit_prompt": False,
                    "can_change_provider": False,
                    "can_change_model": False,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        assigned_tools = []
        for capability in capabilities:
            tool_name = CAPABILITY_TO_TOOL.get(capability)
            if tool_name and tool_name not in assigned_tools:
                db.add(
                    AgentToolAssignment(
                        agent_id=agent.id,
                        tool_name=tool_name,
                        config={},
                        enabled=True,
                    )
                )
                assigned_tools.append(tool_name)

        for channel_type in channels:
            db.add(
                AgentChannel(
                    company_id=company_id,
                    agent_id=agent.id,
                    channel_type=channel_type,
                    config={},
                    enabled=False,
                )
            )

        solution = CompanySolution(
            company_id=company_id,
            service_code="ai_agents",
            name=data.name.strip(),
            package_tier=package_tier,
            status="setup",
            description=data.description,
            capabilities=capabilities,
            channels=channels,
            configuration={
                "provider": data.provider,
                "model": data.model,
                "assigned_tools": assigned_tools,
            },
            linked_agent_id=agent.id,
        )
        db.add(solution)
        db.commit()
        db.refresh(solution)

        result = serialize_solution(solution)
        result["provisioning"] = {
            "agent_id": agent.id,
            "agent_enabled": agent.enabled,
            "channels_created_disabled": channels,
            "tools_assigned": assigned_tools,
            "next_step": "Configure channels and company knowledge, then run readiness.",
        }
        return result
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{solution_id}/status")
def update_solution_status(
    solution_id: int,
    data: SolutionStatusUpdate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        status = validate_choice(data.status, ALLOWED_STATUSES, "status")
        item = (
            db.query(CompanySolution)
            .filter(CompanySolution.id == solution_id)
            .first()
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Solution not found")
        item.status = status
        db.commit()
        db.refresh(item)
        return serialize_solution(item)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
