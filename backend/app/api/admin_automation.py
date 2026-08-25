from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.automation.models import AutomationWorkflow, AutomationRun

router = APIRouter(prefix="/admin/automation", tags=["Xvond Admin - Automation"])

ALLOWED_TRIGGERS = {"manual", "webhook", "schedule", "event"}
ALLOWED_STEP_TYPES = {"ai", "integration", "tool", "condition", "webhook", "transform"}


class WorkflowCreate(BaseModel):
    name: str
    trigger_type: str = "manual"
    trigger_config: dict = Field(default_factory=dict)
    steps: list[dict] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: str | None = None
    trigger_type: str | None = None
    trigger_config: dict | None = None
    steps: list[dict] | None = None
    enabled: bool | None = None


def require_company(db, company_id: int):
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def validate_workflow(trigger_type: str, steps: list[dict]):
    trigger = (trigger_type or "").strip().lower()
    if trigger not in ALLOWED_TRIGGERS:
        raise HTTPException(status_code=400, detail="Unsupported automation trigger")
    for index, step in enumerate(steps or []):
        step_type = str(step.get("type", "")).strip().lower()
        if step_type not in ALLOWED_STEP_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported step type at {index}")
    return trigger


def serialize(item):
    return {
        "id": item.id,
        "company_id": item.company_id,
        "name": item.name,
        "trigger_type": item.trigger_type,
        "trigger_config": item.trigger_config,
        "steps": item.steps,
        "enabled": item.enabled,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/companies/{company_id}")
def list_workflows(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        items = db.query(AutomationWorkflow).filter(
            AutomationWorkflow.company_id == company_id
        ).order_by(AutomationWorkflow.id.desc()).all()
        return {"company_id": company_id, "workflows": [serialize(x) for x in items]}
    finally:
        db.close()


@router.post("/companies/{company_id}")
def create_workflow(company_id: int, data: WorkflowCreate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Workflow name is required")
        trigger = validate_workflow(data.trigger_type, data.steps)
        item = AutomationWorkflow(
            company_id=company_id,
            name=name,
            trigger_type=trigger,
            trigger_config=data.trigger_config or {},
            steps=data.steps or [],
            enabled=False,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return serialize(item)
    finally:
        db.close()


@router.patch("/{workflow_id}")
def update_workflow(workflow_id: int, data: WorkflowUpdate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        item = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
        if item is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        if data.name is not None:
            item.name = data.name.strip()
        new_trigger = data.trigger_type if data.trigger_type is not None else item.trigger_type
        new_steps = data.steps if data.steps is not None else item.steps
        item.trigger_type = validate_workflow(new_trigger, new_steps)
        if data.trigger_config is not None:
            item.trigger_config = data.trigger_config
        if data.steps is not None:
            item.steps = data.steps
        if data.enabled is not None:
            item.enabled = data.enabled
        db.commit()
        db.refresh(item)
        return serialize(item)
    finally:
        db.close()


@router.get("/companies/{company_id}/runs")
def list_runs(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        items = db.query(AutomationRun).filter(
            AutomationRun.company_id == company_id
        ).order_by(AutomationRun.id.desc()).limit(200).all()
        return {"runs": [{
            "id": x.id,
            "workflow_id": x.workflow_id,
            "status": x.status,
            "created_at": x.created_at,
            "finished_at": x.finished_at,
            "error_message": x.error_message,
        } for x in items]}
    finally:
        db.close()
