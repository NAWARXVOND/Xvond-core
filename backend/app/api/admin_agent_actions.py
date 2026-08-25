import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.tools.business_models import ActionRequest
from backend.app.modules.tools.models import AgentToolAssignment

router = APIRouter(prefix="/admin/agent-actions", tags=["Xvond Admin - Agent Actions"])
VALID_REQUEST_STATUSES = {"awaiting_confirmation", "new", "pending_human", "in_progress", "confirmed", "processing", "completed", "cancelled"}
VALID_DESTINATIONS = {"unconfigured", "xvond_internal", "human_handoff", "integration"}
VALID_AVAILABILITY = {"none", "xvond_schedule", "integration"}


def _field(key, label, field_type="text", role="", required=True):
    return {"key": key, "label": label, "type": field_type, "role": role, "required": required}


TEMPLATES = [
    {
        "id": "catering",
        "label": "Catering / Events",
        "business_types": ["catering", "events", "hospitality"],
        "actions": [
            {
                "key": "catering_request", "label": "Catering Request", "enabled": True,
                "description": "Collect and register a catering request for an event.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("event_type", "Event type"), _field("event_date", "Event date", "date", "date"), _field("guest_count", "Guest count", "number"), _field("location", "Location"), _field("request", "Requested service / package"), _field("notes", "Notes", required=False)],
                "confirmation_required": True,
                "availability": {"mode": "none"},
                "destination": {"type": "xvond_internal"},
            },
            {
                "key": "consultation_booking", "label": "Consultation Booking", "enabled": False,
                "description": "Book a real consultation slot after checking configured availability.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("date", "Date", "date", "date"), _field("time", "Time", "time", "time"), _field("notes", "Notes", required=False)],
                "confirmation_required": True,
                "availability": {"mode": "xvond_schedule", "date_field": "date", "time_field": "time", "schedule": {"weekdays": [], "start": "", "end": "", "slot_minutes": 30, "capacity": 1}},
                "destination": {"type": "xvond_internal"},
            },
        ],
    },
    {
        "id": "salon",
        "label": "Salon / Beauty",
        "business_types": ["salon / beauty", "salon", "beauty"],
        "actions": [
            {
                "key": "book_appointment", "label": "Book Appointment", "enabled": False,
                "description": "Check real availability and create an appointment.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("service", "Service"), _field("date", "Date", "date", "date"), _field("time", "Time", "time", "time"), _field("staff", "Preferred specialist", required=False)],
                "confirmation_required": True,
                "availability": {"mode": "xvond_schedule", "date_field": "date", "time_field": "time", "resource_field": "staff", "schedule": {"weekdays": [], "start": "", "end": "", "slot_minutes": 30, "capacity": 1}},
                "destination": {"type": "xvond_internal"},
            },
            {
                "key": "callback_request", "label": "Callback Request", "enabled": True,
                "description": "Register a request for the salon team to call the customer.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("reason", "Reason")],
                "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "xvond_internal"},
            },
        ],
    },
    {
        "id": "restaurant",
        "label": "Restaurant / Cafe",
        "business_types": ["restaurant / cafe", "restaurant", "cafe"],
        "actions": [
            {
                "key": "food_order", "label": "Food Order", "enabled": True,
                "description": "Collect and register a customer order.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("items", "Items / quantities"), _field("fulfillment", "Pickup or delivery"), _field("address", "Delivery address", required=False), _field("notes", "Notes", required=False)],
                "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "xvond_internal"},
            },
            {
                "key": "table_reservation", "label": "Table Reservation", "enabled": False,
                "description": "Check configured table-slot availability and create a reservation.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("guest_count", "Guests", "number"), _field("date", "Date", "date", "date"), _field("time", "Time", "time", "time"), _field("notes", "Notes", required=False)],
                "confirmation_required": True,
                "availability": {"mode": "xvond_schedule", "date_field": "date", "time_field": "time", "schedule": {"weekdays": [], "start": "", "end": "", "slot_minutes": 30, "capacity": 1}},
                "destination": {"type": "xvond_internal"},
            },
        ],
    },
    {
        "id": "hotel",
        "label": "Hotel / Hospitality",
        "business_types": ["hotel / hospitality", "hotel"],
        "actions": [
            {
                "key": "reservation_request", "label": "Reservation Request", "enabled": True,
                "description": "Collect a room reservation request. Connect to the hotel booking system when direct availability confirmation is required.",
                "fields": [_field("customer_name", "Guest name"), _field("phone", "Phone"), _field("check_in", "Check-in", "date"), _field("check_out", "Check-out", "date"), _field("guests", "Guests", "number"), _field("room_type", "Room type", required=False), _field("notes", "Notes", required=False)],
                "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "xvond_internal"},
            }
        ],
    },
    {
        "id": "professional_services",
        "label": "Professional / Service Company",
        "business_types": ["professional services", "legal services", "financial / accounting services", "marketing / media", "technology / software"],
        "actions": [
            {
                "key": "quote_request", "label": "Request Quote", "enabled": True,
                "description": "Collect the information needed for a quotation.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("email", "Email", "email", required=False), _field("service", "Service needed"), _field("requirements", "Requirements"), _field("budget", "Budget", required=False), _field("timeline", "Timeline", required=False)],
                "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "xvond_internal"},
            },
            {
                "key": "consultation_booking", "label": "Consultation Booking", "enabled": False,
                "description": "Book a consultation using configured availability.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("date", "Date", "date", "date"), _field("time", "Time", "time", "time"), _field("topic", "Topic")],
                "confirmation_required": True,
                "availability": {"mode": "xvond_schedule", "date_field": "date", "time_field": "time", "schedule": {"weekdays": [], "start": "", "end": "", "slot_minutes": 30, "capacity": 1}},
                "destination": {"type": "xvond_internal"},
            },
        ],
    },
    {
        "id": "general",
        "label": "General Business",
        "business_types": ["other"],
        "actions": [
            {
                "key": "customer_request", "label": "Customer Request", "enabled": True,
                "description": "Collect and register a structured customer request.",
                "fields": [_field("customer_name", "Customer name"), _field("phone", "Phone"), _field("request", "Request"), _field("notes", "Notes", required=False)],
                "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "xvond_internal"},
            }
        ],
    },
]


class AgentActionsPayload(BaseModel):
    template_id: str | None = None
    actions: list[dict] | None = None
    booking_mode: str | None = None
    booking_fields: list[str] = Field(default_factory=list)
    order_mode: str | None = None
    order_fields: list[str] = Field(default_factory=list)
    lead_enabled: bool | None = None
    lead_fields: list[str] = Field(default_factory=list)


class RequestStatusUpdate(BaseModel):
    status: str


def _assignment(db, agent_id, name):
    return db.query(AgentToolAssignment).filter(AgentToolAssignment.agent_id == agent_id, AgentToolAssignment.tool_name == name).first()


def _set(db, agent_id, name, enabled, config):
    row = _assignment(db, agent_id, name)
    if row:
        row.enabled = enabled
        row.config = config
    else:
        db.add(AgentToolAssignment(agent_id=agent_id, tool_name=name, enabled=enabled, config=config))


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return value[:80]


def _normalize_fields(raw) -> list[dict]:
    result = []
    seen = set()
    for item in raw or []:
        if isinstance(item, str):
            key = _slug(item)
            data = {"key": key, "label": item.strip().replace("_", " "), "type": "text", "role": "", "required": True}
        elif isinstance(item, dict):
            key = _slug(item.get("key") or item.get("name"))
            data = {
                "key": key,
                "label": str(item.get("label") or key.replace("_", " ")).strip()[:120],
                "type": str(item.get("type") or "text").strip()[:30],
                "role": str(item.get("role") or "").strip()[:30],
                "required": bool(item.get("required", True)),
            }
        else:
            continue
        if key and key not in seen:
            seen.add(key)
            result.append(data)
    return result[:50]


def _normalize_action(item: dict) -> dict:
    key = _slug(item.get("key") or item.get("name") or item.get("label"))
    if not key:
        raise HTTPException(400, "Each action needs a key or name")
    destination = dict(item.get("destination") or {})
    destination_type = str(destination.get("type") or "unconfigured").strip()
    if destination_type not in VALID_DESTINATIONS:
        raise HTTPException(400, f"Invalid destination for {key}")
    destination["type"] = destination_type
    availability = dict(item.get("availability") or {})
    availability_mode = str(availability.get("mode") or "none").strip()
    if availability_mode not in VALID_AVAILABILITY:
        raise HTTPException(400, f"Invalid availability mode for {key}")
    availability["mode"] = availability_mode
    fields = _normalize_fields(item.get("fields") or item.get("required_fields") or [])
    return {
        "key": key,
        "label": str(item.get("label") or key.replace("_", " ")).strip()[:150],
        "description": str(item.get("description") or "").strip()[:1500],
        "enabled": bool(item.get("enabled", True)),
        "fields": fields,
        "confirmation_required": bool(item.get("confirmation_required", True)),
        "availability": availability,
        "destination": destination,
    }


def _readiness(action: dict) -> list[str]:
    issues = []
    if not action.get("enabled", True):
        return issues
    destination = action.get("destination") or {}
    if destination.get("type") == "unconfigured":
        issues.append("Choose a real destination")
    if destination.get("type") == "integration" and not destination.get("integration_id"):
        issues.append("Choose an integration")
    availability = action.get("availability") or {}
    if availability.get("mode") == "xvond_schedule":
        schedule = availability.get("schedule") or {}
        if not availability.get("date_field") or not availability.get("time_field"):
            issues.append("Choose date/time fields for availability")
        if not schedule.get("weekdays") or not schedule.get("start") or not schedule.get("end"):
            issues.append("Configure working days and hours")
    if availability.get("mode") == "integration" and destination.get("type") != "integration":
        issues.append("Integration availability requires an integration destination")
    return issues


def _legacy_actions(data: AgentActionsPayload) -> list[dict]:
    actions = []
    if data.booking_mode and data.booking_mode != "disabled":
        actions.append({"key": "booking", "label": "Booking", "enabled": True, "fields": data.booking_fields, "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "human_handoff" if data.booking_mode == "human_handoff" else "xvond_internal"}})
    if data.order_mode and data.order_mode != "disabled":
        actions.append({"key": "order", "label": "Order", "enabled": True, "fields": data.order_fields, "confirmation_required": True, "availability": {"mode": "none"}, "destination": {"type": "human_handoff" if data.order_mode == "human_handoff" else "xvond_internal"}})
    if data.lead_enabled:
        actions.append({"key": "lead", "label": "Lead", "enabled": True, "fields": data.lead_fields or ["name", "phone"], "confirmation_required": False, "availability": {"mode": "none"}, "destination": {"type": "xvond_internal"}})
    return actions


@router.get("/templates/catalog")
def templates_catalog(current_admin: User = Depends(require_xvond_admin)):
    return {"templates": TEMPLATES}


@router.get("/{agent_id}")
def get_actions(agent_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            raise HTTPException(404, "AI employee not found")
        assignment = _assignment(db, agent_id, "action_request")
        config = reveal_config(assignment.config) if assignment else {}
        stored = (config or {}).get("actions") or {}
        actions = []
        for key, value in stored.items():
            if isinstance(value, dict):
                item = {"key": key, **value}
                item["readiness_issues"] = _readiness(item)
                actions.append(item)
        return {"agent_id": agent_id, "template_id": (config or {}).get("template_id"), "actions": actions, "ready": all(not x.get("readiness_issues") for x in actions if x.get("enabled", True))}
    finally:
        db.close()


@router.put("/{agent_id}")
def update_actions(agent_id: int, data: AgentActionsPayload, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            raise HTTPException(404, "AI employee not found")
        raw_actions = data.actions if data.actions is not None else _legacy_actions(data)
        normalized = [_normalize_action(x) for x in raw_actions]
        by_key = {x["key"]: {k: v for k, v in x.items() if k != "key"} for x in normalized}
        _set(db, agent_id, "action_request", bool(any(x.get("enabled", True) for x in normalized)), {"approval_required": False, "template_id": data.template_id, "actions": by_key})
        # Legacy specialized tools must not compete with the generic action engine.
        for legacy in ("booking", "order"):
            row = _assignment(db, agent_id, legacy)
            if row:
                row.enabled = False
        _set(db, agent_id, "human_handoff", True, {"approval_required": False})
        db.commit()
        return {"status": "updated", "actions": [{**x, "readiness_issues": _readiness(x)} for x in normalized]}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/companies/{company_id}/requests")
def list_requests(company_id: int, agent_id: int | None = None, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        query = db.query(ActionRequest).filter(ActionRequest.company_id == company_id)
        if agent_id is not None:
            query = query.filter(ActionRequest.agent_id == agent_id)
        items = query.order_by(ActionRequest.id.desc()).limit(500).all()
        return {"requests": [{"id": x.id, "agent_id": x.agent_id, "conversation_id": x.conversation_id, "action_type": x.action_type, "details": x.details, "summary": x.summary, "status": x.status, "created_at": x.created_at} for x in items]}
    finally:
        db.close()


@router.patch("/requests/{request_id}")
def update_request_status(request_id: int, data: RequestStatusUpdate, current_admin: User = Depends(require_xvond_admin)):
    if data.status not in VALID_REQUEST_STATUSES:
        raise HTTPException(400, "Invalid request status")
    db = SessionLocal()
    try:
        item = db.query(ActionRequest).filter(ActionRequest.id == request_id).first()
        if not item:
            raise HTTPException(404, "Action request not found")
        item.status = data.status
        db.commit()
        return {"status": "updated"}
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
