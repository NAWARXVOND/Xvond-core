from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.app.core.config.settings import settings
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.tools.action_request import _internal_slots
from backend.app.modules.tools.business_models import ActionRequest


router = APIRouter(prefix="/internal/workflow", tags=["Xvond Internal Workflow"])


class InternalWorkflowAction(BaseModel):
    company_id: int
    agent_id: int
    conversation_id: int | None = None
    action: str
    request_id: str
    data: dict


def _require_workflow_secret(value: str | None) -> None:
    expected = str(settings.N8N_SHARED_SECRET or "")
    if not expected or value != expected:
        raise HTTPException(401, "Unauthorized workflow request")


def _native_receipt(request: ActionRequest) -> dict:
    details = request.details or {}
    value = details.get("_xvond_native_execution")
    return dict(value) if isinstance(value, dict) else {}


@router.post("/xvond-internal")
def execute_xvond_internal(
    payload: InternalWorkflowAction,
    x_xvond_n8n_secret: str | None = Header(default=None),
):
    _require_workflow_secret(x_xvond_n8n_secret)
    action_type, _, operation = str(payload.action or "").rpartition(".")
    if operation not in {"check_availability", "execute", "cancel"} or not action_type:
        raise HTTPException(400, "Unsupported internal workflow action")

    data = payload.data or {}
    action_config = data.get("action_config") or {}
    if not isinstance(action_config, dict):
        raise HTTPException(400, "Invalid action configuration")
    if str(action_config.get("destination", {}).get("type") or "") != "xvond_internal":
        raise HTTPException(400, "Action is not routed to Xvond Internal")

    db = SessionLocal()
    try:
        if operation == "check_availability":
            details = data.get("details") or {}
            result = _internal_slots(
                db,
                {"company_id": payload.company_id, "agent_id": payload.agent_id},
                action_type,
                action_config,
                details,
            )
            return {
                "success": result.success,
                "action": payload.action,
                "request_id": payload.request_id,
                "data": result.data or {},
                "error": result.error,
            }

        action_request_id = data.get("request_id")
        if not action_request_id:
            raise HTTPException(400, "Internal execution requires action request id")
        request = (
            db.query(ActionRequest)
            .filter(
                ActionRequest.id == int(action_request_id),
                ActionRequest.company_id == payload.company_id,
                ActionRequest.agent_id == payload.agent_id,
                ActionRequest.action_type == action_type,
            )
            .first()
        )
        if request is None:
            raise HTTPException(404, "Business request not found")

        idempotency_key = str(data.get("idempotency_key") or payload.request_id or "").strip()
        if not idempotency_key:
            raise HTTPException(400, "Idempotency key is required")
        current = _native_receipt(request)
        if current.get("idempotency_key") == idempotency_key and current.get("operation") == operation:
            return {
                "success": True,
                "action": payload.action,
                "request_id": payload.request_id,
                "data": {"native_execution": current, "already_executed": True},
                "error": None,
            }

        if operation == "execute":
            availability = action_config.get("availability") or {}
            if str(availability.get("mode") or "none") == "xvond_schedule":
                availability_result = _internal_slots(
                    db,
                    {"company_id": payload.company_id, "agent_id": payload.agent_id},
                    action_type,
                    action_config,
                    request.details or {},
                )
                if not availability_result.success or not (availability_result.data or {}).get("available"):
                    return {
                        "success": False,
                        "action": payload.action,
                        "request_id": payload.request_id,
                        "data": availability_result.data or {},
                        "error": availability_result.error or "Requested time is no longer available",
                    }

        receipt = {
            "operation": operation,
            "state": "confirmed",
            "idempotency_key": idempotency_key,
            "executed_at": datetime.utcnow().isoformat(),
            "destination": "xvond_internal",
        }
        details = dict(request.details or {})
        details["_xvond_native_execution"] = receipt
        request.details = details
        db.commit()
        return {
            "success": True,
            "action": payload.action,
            "request_id": payload.request_id,
            "data": {"native_execution": receipt, "action_request_id": request.id},
            "error": None,
        }
    finally:
        db.close()
