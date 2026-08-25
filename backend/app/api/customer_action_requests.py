from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.tools.business_models import ActionRequest

router = APIRouter(prefix="/customer/action-requests", tags=["Customer AI Operations"])
ALLOWED_STATUSES = {"new", "pending_human", "in_progress", "confirmed", "processing", "completed", "cancelled"}


class StatusUpdate(BaseModel):
    status: str


def _company_id(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(403, "Customer company required")
    return user.company_id


def _serialize(item: ActionRequest) -> dict:
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "conversation_id": item.conversation_id,
        "action_type": item.action_type,
        "details": item.details or {},
        "summary": item.summary,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.get("")
def list_requests(agent_id: int | None = None, current_user: User = Depends(require_customer_manager)):
    db = SessionLocal()
    try:
        company_id = _company_id(current_user)
        query = db.query(ActionRequest).filter(ActionRequest.company_id == company_id)
        if agent_id is not None:
            query = query.filter(ActionRequest.agent_id == agent_id)
        items = query.order_by(ActionRequest.id.desc()).limit(1000).all()
        return {"requests": [_serialize(item) for item in items]}
    finally:
        db.close()


@router.patch("/{request_id}")
def update_status(request_id: int, data: StatusUpdate, current_user: User = Depends(require_customer_manager)):
    status = data.status.strip().lower()
    if status not in ALLOWED_STATUSES:
        raise HTTPException(400, "Invalid operation status")
    db = SessionLocal()
    try:
        company_id = _company_id(current_user)
        item = db.query(ActionRequest).filter(ActionRequest.id == request_id, ActionRequest.company_id == company_id).first()
        if item is None:
            raise HTTPException(404, "Operation not found")
        if item.status == "awaiting_confirmation":
            raise HTTPException(409, "Customer confirmation is still pending")
        item.status = status
        db.commit()
        db.refresh(item)
        return _serialize(item)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
