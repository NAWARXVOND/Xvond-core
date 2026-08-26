from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.tools.business_models import ActionRequest
from backend.app.modules.tools.models import AgentToolAssignment

router = APIRouter(prefix="/customer/action-requests", tags=["Customer AI Operations"])
ALLOWED_STATUSES = {"new", "pending_human", "in_progress", "confirmed", "processing", "completed", "cancelled"}


class StatusUpdate(BaseModel):
    status: str


def _company_id(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(403, "Customer company required")
    return user.company_id


def _action_catalog(db, company_id: int) -> dict[tuple[int, str], dict]:
    agent_ids = [
        row[0]
        for row in db.query(AIAgent.id).filter(AIAgent.company_id == company_id).all()
    ]
    if not agent_ids:
        return {}
    assignments = (
        db.query(AgentToolAssignment)
        .filter(
            AgentToolAssignment.agent_id.in_(agent_ids),
            AgentToolAssignment.tool_name == "action_request",
        )
        .all()
    )
    result = {}
    for assignment in assignments:
        config = reveal_config(assignment.config) or {}
        actions = config.get("actions") or {}
        for key, value in actions.items():
            if not isinstance(value, dict):
                continue
            result[(assignment.agent_id, str(key))] = {
                "module": str(value.get("module") or "").strip(),
                "label": str(value.get("label") or key).strip(),
            }
    return result


def _serialize(item: ActionRequest, catalog: dict[tuple[int, str], dict]) -> dict:
    action = catalog.get((item.agent_id, item.action_type), {})
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "conversation_id": item.conversation_id,
        "action_type": item.action_type,
        "action_label": action.get("label") or item.action_type.replace("_", " ").title(),
        "module": action.get("module") or None,
        "details": item.details or {},
        "summary": item.summary,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.get("")
def list_requests(
    agent_id: int | None = None,
    module: str | None = None,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        company_id = _company_id(current_user)
        catalog = _action_catalog(db, company_id)
        query = db.query(ActionRequest).filter(ActionRequest.company_id == company_id)
        if agent_id is not None:
            query = query.filter(ActionRequest.agent_id == agent_id)
        items = query.order_by(ActionRequest.id.desc()).limit(1000).all()
        serialized = [_serialize(item, catalog) for item in items]
        module_name = str(module or "").strip()
        if module_name:
            serialized = [item for item in serialized if item.get("module") == module_name]
        return {"requests": serialized}
    finally:
        db.close()


@router.patch("/{request_id}")
def update_status(
    request_id: int,
    data: StatusUpdate,
    current_user: User = Depends(require_customer_manager),
):
    status = data.status.strip().lower()
    if status not in ALLOWED_STATUSES:
        raise HTTPException(400, "Invalid operation status")
    db = SessionLocal()
    try:
        company_id = _company_id(current_user)
        item = db.query(ActionRequest).filter(
            ActionRequest.id == request_id,
            ActionRequest.company_id == company_id,
        ).first()
        if item is None:
            raise HTTPException(404, "Operation not found")
        if item.status == "awaiting_confirmation":
            raise HTTPException(409, "Customer confirmation is still pending")
        item.status = status
        db.commit()
        db.refresh(item)
        return _serialize(item, _action_catalog(db, company_id))
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
