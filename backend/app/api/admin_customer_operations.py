from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage, AIUsage
from backend.app.modules.customer_ops.models import CustomerRecord, NotificationEvent, NotificationPreference
from backend.app.modules.tools.business_models import ActionRequest, Booking, HumanHandoff, Lead, Order

router = APIRouter(prefix="/admin/customer-operations", tags=["Xvond Admin - Customer Operations"])

DEFAULT_EVENTS = [
    "booking_new",
    "order_new",
    "lead_new",
    "handoff_pending",
    "operation_attention",
    "ai_failure",
]


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    tags: list[str] = []
    notes: str | None = None


class NotificationPreferenceUpdate(BaseModel):
    enabled: bool = True
    event_types: list[str] = DEFAULT_EVENTS
    destinations: list[str] = ["dashboard"]
    email: str | None = None
    whatsapp: str | None = None
    webhook_url: str | None = None


def _clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _identity(*, phone=None, email=None, external=None):
    if _clean(phone):
        return "phone:" + "".join(ch for ch in str(phone) if ch.isdigit() or ch == "+").lower()
    if _clean(email):
        return "email:" + str(email).strip().lower()
    if _clean(external):
        return "external:" + str(external).strip().lower()
    return None


def _upsert_customer(db, company_id: int, *, name=None, phone=None, email=None, external=None, channel=None, seen_at=None):
    key = _identity(phone=phone, email=email, external=external)
    if not key:
        return None
    row = db.query(CustomerRecord).filter(CustomerRecord.company_id == company_id, CustomerRecord.identity_key == key).first()
    now = seen_at or datetime.utcnow()
    if row is None:
        row = CustomerRecord(
            company_id=company_id,
            identity_key=key,
            name=_clean(name),
            phone=_clean(phone),
            email=_clean(email),
            external_contact_id=_clean(external),
            channel=_clean(channel),
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
    else:
        if _clean(name) and not row.name:
            row.name = _clean(name)
        if _clean(phone):
            row.phone = _clean(phone)
        if _clean(email):
            row.email = _clean(email)
        if _clean(external):
            row.external_contact_id = _clean(external)
        if _clean(channel):
            row.channel = _clean(channel)
        if now and (row.last_seen_at is None or now > row.last_seen_at):
            row.last_seen_at = now
    return row


def _event(db, company_id: int, key: str, event_type: str, title: str, *, message=None, severity="info", payload=None, created_at=None):
    existing = db.query(NotificationEvent).filter(NotificationEvent.company_id == company_id, NotificationEvent.event_key == key).first()
    if existing:
        return existing
    row = NotificationEvent(
        company_id=company_id,
        event_key=key,
        event_type=event_type,
        severity=severity,
        title=title,
        message=message,
        payload=payload or {},
        created_at=created_at or datetime.utcnow(),
    )
    db.add(row)
    return row


def sync_company(db, company_id: int):
    for lead in db.query(Lead).filter(Lead.company_id == company_id).all():
        _upsert_customer(db, company_id, name=lead.name, phone=lead.phone, email=lead.email, seen_at=lead.created_at)
        _event(db, company_id, f"lead:{lead.id}", "lead_new", "New lead", message=lead.name or lead.interest, payload={"lead_id": lead.id}, created_at=lead.created_at)

    for booking in db.query(Booking).filter(Booking.company_id == company_id).all():
        _upsert_customer(db, company_id, name=booking.customer_name, phone=booking.phone, seen_at=booking.created_at)
        _event(db, company_id, f"booking:{booking.id}", "booking_new", "New booking", message=booking.customer_name or booking.service, payload={"booking_id": booking.id}, created_at=booking.created_at)

    for order in db.query(Order).filter(Order.company_id == company_id).all():
        _upsert_customer(db, company_id, name=order.customer_name, phone=order.phone, seen_at=order.created_at)
        _event(db, company_id, f"order:{order.id}", "order_new", "New order", message=order.customer_name, payload={"order_id": order.id}, created_at=order.created_at)

    for conversation in db.query(AIConversation).filter(AIConversation.company_id == company_id).all():
        if conversation.external_contact_id:
            _upsert_customer(
                db,
                company_id,
                external=conversation.external_contact_id,
                channel=conversation.channel_type,
                seen_at=conversation.created_at,
            )

    for handoff in db.query(HumanHandoff).filter(HumanHandoff.company_id == company_id, HumanHandoff.status == "pending").all():
        _event(db, company_id, f"handoff:{handoff.id}", "handoff_pending", "Human handoff waiting", message=handoff.reason, severity="warning", payload={"handoff_id": handoff.id, "conversation_id": handoff.conversation_id}, created_at=handoff.created_at)

    attention_states = ["external_failed", "executing", "cancelling", "pending_human"]
    for request in db.query(ActionRequest).filter(ActionRequest.company_id == company_id, ActionRequest.status.in_(attention_states)).all():
        _event(db, company_id, f"operation:{request.id}:{request.status}", "operation_attention", "Operation needs attention", message=request.summary or request.action_type, severity="warning", payload={"request_id": request.id, "status": request.status}, created_at=request.created_at)

    for usage in db.query(AIUsage).filter(AIUsage.company_id == company_id, AIUsage.status == "failed").all():
        _event(db, company_id, f"ai-failure:{usage.id}", "ai_failure", "AI request failed", message=usage.error_message, severity="critical", payload={"usage_id": usage.id, "agent_id": usage.agent_id}, created_at=usage.created_at)

    pref = db.query(NotificationPreference).filter(NotificationPreference.company_id == company_id).first()
    if pref is None:
        db.add(NotificationPreference(company_id=company_id, event_types=list(DEFAULT_EVENTS), destinations=["dashboard"]))
    db.flush()


def _customer_metrics(db, company_id: int, customer: CustomerRecord):
    phone = customer.phone
    email = customer.email
    leads = db.query(Lead).filter(Lead.company_id == company_id)
    bookings = db.query(Booking).filter(Booking.company_id == company_id)
    orders = db.query(Order).filter(Order.company_id == company_id)
    if phone:
        leads = leads.filter(Lead.phone == phone)
        bookings = bookings.filter(Booking.phone == phone)
        orders = orders.filter(Order.phone == phone)
    elif email:
        leads = leads.filter(Lead.email == email)
        bookings = bookings.filter(False)
        orders = orders.filter(False)
    else:
        return {"leads": 0, "bookings": 0, "orders": 0, "conversations": 0}

    conversation_count = 0
    if customer.external_contact_id:
        conversation_count = db.query(func.count(AIConversation.id)).filter(
            AIConversation.company_id == company_id,
            AIConversation.external_contact_id == customer.external_contact_id,
        ).scalar() or 0
    return {
        "leads": leads.count(),
        "bookings": bookings.count(),
        "orders": orders.count(),
        "conversations": int(conversation_count),
    }


@router.get("/companies/{company_id}/customers")
def customers(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        sync_company(db, company_id)
        db.commit()
        rows = db.query(CustomerRecord).filter(CustomerRecord.company_id == company_id).order_by(CustomerRecord.last_seen_at.desc()).all()
        return {"customers": [{
            "id": x.id,
            "name": x.name,
            "phone": x.phone,
            "email": x.email,
            "external_contact_id": x.external_contact_id,
            "channel": x.channel,
            "tags": x.tags or [],
            "notes": x.notes,
            "first_seen_at": x.first_seen_at,
            "last_seen_at": x.last_seen_at,
            "metrics": _customer_metrics(db, company_id, x),
        } for x in rows]}
    finally:
        db.close()


@router.get("/companies/{company_id}/customers/{customer_id}")
def customer_detail(company_id: int, customer_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        sync_company(db, company_id)
        row = db.query(CustomerRecord).filter(CustomerRecord.company_id == company_id, CustomerRecord.id == customer_id).first()
        if not row:
            raise HTTPException(404, "Customer not found")
        phone, email = row.phone, row.email
        leads = db.query(Lead).filter(Lead.company_id == company_id, Lead.phone == phone).order_by(Lead.created_at.desc()).all() if phone else db.query(Lead).filter(Lead.company_id == company_id, Lead.email == email).order_by(Lead.created_at.desc()).all() if email else []
        bookings = db.query(Booking).filter(Booking.company_id == company_id, Booking.phone == phone).order_by(Booking.created_at.desc()).all() if phone else []
        orders = db.query(Order).filter(Order.company_id == company_id, Order.phone == phone).order_by(Order.created_at.desc()).all() if phone else []
        conversations = db.query(AIConversation).filter(AIConversation.company_id == company_id, AIConversation.external_contact_id == row.external_contact_id).order_by(AIConversation.created_at.desc()).all() if row.external_contact_id else []
        return {
            "customer": {"id": row.id, "name": row.name, "phone": row.phone, "email": row.email, "channel": row.channel, "tags": row.tags or [], "notes": row.notes, "first_seen_at": row.first_seen_at, "last_seen_at": row.last_seen_at},
            "leads": [{"id": x.id, "interest": x.interest, "status": x.status, "created_at": x.created_at} for x in leads],
            "bookings": [{"id": x.id, "service": x.service, "date": x.booking_date, "time": x.booking_time, "status": x.status, "created_at": x.created_at} for x in bookings],
            "orders": [{"id": x.id, "items": x.items, "status": x.status, "created_at": x.created_at} for x in orders],
            "conversations": [{"id": x.id, "agent_id": x.agent_id, "channel": x.channel_type, "title": x.title, "created_at": x.created_at} for x in conversations],
        }
    finally:
        db.close()


@router.put("/companies/{company_id}/customers/{customer_id}")
def update_customer(company_id: int, customer_id: int, data: CustomerUpdate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        row = db.query(CustomerRecord).filter(CustomerRecord.company_id == company_id, CustomerRecord.id == customer_id).first()
        if not row:
            raise HTTPException(404, "Customer not found")
        row.name = _clean(data.name)
        row.phone = _clean(data.phone)
        row.email = _clean(data.email)
        row.tags = sorted(set(x.strip() for x in data.tags if x and x.strip()))
        row.notes = _clean(data.notes)
        db.commit()
        return {"status": "updated", "customer_id": row.id}
    finally:
        db.close()


@router.get("/companies/{company_id}/notifications")
def notifications(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        sync_company(db, company_id)
        db.commit()
        pref = db.query(NotificationPreference).filter(NotificationPreference.company_id == company_id).first()
        enabled_types = set(pref.event_types or DEFAULT_EVENTS) if pref and pref.enabled else set()
        rows = db.query(NotificationEvent).filter(NotificationEvent.company_id == company_id).order_by(NotificationEvent.created_at.desc()).limit(200).all()
        rows = [x for x in rows if x.event_type in enabled_types]
        return {
            "unread": sum(1 for x in rows if not x.read),
            "preferences": {"enabled": pref.enabled, "event_types": pref.event_types or [], "destinations": pref.destinations or [], "email": pref.email, "whatsapp": pref.whatsapp, "webhook_url": pref.webhook_url} if pref else None,
            "events": [{"id": x.id, "event_type": x.event_type, "severity": x.severity, "title": x.title, "message": x.message, "payload": x.payload or {}, "read": x.read, "created_at": x.created_at} for x in rows],
        }
    finally:
        db.close()


@router.put("/companies/{company_id}/notification-preferences")
def update_notification_preferences(company_id: int, data: NotificationPreferenceUpdate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        row = db.query(NotificationPreference).filter(NotificationPreference.company_id == company_id).first()
        if row is None:
            row = NotificationPreference(company_id=company_id)
            db.add(row)
        allowed_destinations = {"dashboard", "email", "whatsapp", "webhook"}
        row.enabled = data.enabled
        row.event_types = [x for x in data.event_types if x in DEFAULT_EVENTS]
        row.destinations = [x for x in data.destinations if x in allowed_destinations]
        row.email = _clean(data.email)
        row.whatsapp = _clean(data.whatsapp)
        row.webhook_url = _clean(data.webhook_url)
        db.commit()
        return {"status": "updated"}
    finally:
        db.close()


@router.post("/companies/{company_id}/notifications/read-all")
def read_all_notifications(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        db.query(NotificationEvent).filter(NotificationEvent.company_id == company_id, NotificationEvent.read.is_(False)).update({NotificationEvent.read: True}, synchronize_session=False)
        db.commit()
        return {"status": "updated"}
    finally:
        db.close()


@router.get("/companies/{company_id}/analytics")
def business_analytics(company_id: int, days: int = 30, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        safe_days = max(1, min(int(days), 365))
        since = datetime.utcnow() - timedelta(days=safe_days)
        conversations = db.query(AIConversation).filter(AIConversation.company_id == company_id, AIConversation.created_at >= since).all()
        bookings = db.query(Booking).filter(Booking.company_id == company_id, Booking.created_at >= since).all()
        orders = db.query(Order).filter(Order.company_id == company_id, Order.created_at >= since).all()
        leads = db.query(Lead).filter(Lead.company_id == company_id, Lead.created_at >= since).all()
        handoffs = db.query(HumanHandoff).filter(HumanHandoff.company_id == company_id, HumanHandoff.created_at >= since).all()
        usage = db.query(AIUsage).filter(AIUsage.company_id == company_id, AIUsage.created_at >= since).all()
        operations = db.query(ActionRequest).filter(ActionRequest.company_id == company_id, ActionRequest.created_at >= since).all()

        completed_ops = sum(1 for x in operations if x.status == "completed")
        conversion_base = len(conversations) or 1
        conversion_events = len(bookings) + len(orders) + len(leads)
        by_channel = Counter((x.channel_type or "internal") for x in conversations)
        by_agent = Counter(x.agent_id for x in conversations)
        agent_names = {x.id: x.name for x in db.query(AIAgent).filter(AIAgent.company_id == company_id).all()}
        daily = defaultdict(lambda: {"conversations": 0, "bookings": 0, "orders": 0, "leads": 0})
        for x in conversations: daily[x.created_at.date().isoformat()]["conversations"] += 1
        for x in bookings: daily[x.created_at.date().isoformat()]["bookings"] += 1
        for x in orders: daily[x.created_at.date().isoformat()]["orders"] += 1
        for x in leads: daily[x.created_at.date().isoformat()]["leads"] += 1
        total_cost = sum((Decimal(x.provider_cost or 0) for x in usage), Decimal("0"))
        total_tokens = sum(int(x.total_tokens or 0) for x in usage)
        failures = sum(1 for x in usage if x.status == "failed")

        return {
            "days": safe_days,
            "kpis": {
                "conversations": len(conversations),
                "bookings": len(bookings),
                "orders": len(orders),
                "leads": len(leads),
                "handoffs": len(handoffs),
                "conversion_rate": round((conversion_events / conversion_base) * 100, 2),
                "handoff_rate": round((len(handoffs) / conversion_base) * 100, 2),
                "completed_operations": completed_ops,
                "ai_requests": len(usage),
                "ai_failures": failures,
                "tokens": total_tokens,
                "provider_cost": float(total_cost),
            },
            "channels": [{"channel": key, "conversations": value} for key, value in by_channel.most_common()],
            "agents": [{"agent_id": key, "name": agent_names.get(key, f"AI Employee #{key}"), "conversations": value} for key, value in by_agent.most_common()],
            "daily": [{"date": key, **value} for key, value in sorted(daily.items())],
        }
    finally:
        db.close()
