from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func

from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIUsage
from backend.app.modules.customer_ops.models import (
    CustomerRecord,
    NotificationEvent,
    NotificationPreference,
)
from backend.app.modules.tools.business_models import (
    ActionRequest,
    Booking,
    HumanHandoff,
    Lead,
    Order,
)


DEFAULT_EVENTS = [
    "booking_new",
    "order_new",
    "lead_new",
    "handoff_pending",
    "operation_attention",
    "ai_failure",
]
SUPPORTED_NOTIFICATION_DESTINATIONS = {"dashboard"}


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def normalize_phone(value: str | None) -> str | None:
    text = clean(value)
    if not text:
        return None
    normalized = "".join(ch for ch in text if ch.isdigit() or ch == "+")
    return normalized or None


def identity_key(*, phone=None, email=None, external=None, channel=None) -> str | None:
    normalized_phone = normalize_phone(phone)
    if normalized_phone:
        return "phone:" + normalized_phone.lower()
    normalized_external = clean(external)
    if str(channel or "").strip().lower() == "whatsapp" and normalized_external:
        whatsapp_phone = normalize_phone(normalized_external)
        if whatsapp_phone:
            return "phone:" + whatsapp_phone.lower()
    normalized_email = clean(email)
    if normalized_email:
        return "email:" + normalized_email.lower()
    if normalized_external:
        return "external:" + normalized_external.lower()
    return None


def upsert_customer(
    db,
    company_id: int,
    *,
    name=None,
    phone=None,
    email=None,
    external=None,
    channel=None,
    seen_at=None,
):
    normalized_phone = normalize_phone(phone)
    normalized_external = clean(external)
    normalized_channel = clean(channel)
    if not normalized_phone and str(normalized_channel or "").lower() == "whatsapp":
        normalized_phone = normalize_phone(normalized_external)

    key = identity_key(
        phone=normalized_phone,
        email=email,
        external=normalized_external,
        channel=normalized_channel,
    )
    if not key:
        return None

    row = (
        db.query(CustomerRecord)
        .filter(
            CustomerRecord.company_id == company_id,
            CustomerRecord.identity_key == key,
        )
        .first()
    )
    if row is None and normalized_external:
        row = (
            db.query(CustomerRecord)
            .filter(
                CustomerRecord.company_id == company_id,
                CustomerRecord.external_contact_id == normalized_external,
            )
            .first()
        )
    if row is None and normalized_phone:
        row = (
            db.query(CustomerRecord)
            .filter(
                CustomerRecord.company_id == company_id,
                CustomerRecord.phone == normalized_phone,
            )
            .first()
        )

    now = seen_at or utcnow_naive()
    if row is None:
        row = CustomerRecord(
            company_id=company_id,
            identity_key=key,
            name=clean(name),
            phone=normalized_phone,
            email=clean(email),
            external_contact_id=normalized_external,
            channel=normalized_channel,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
        return row

    # Keep old external-contact identities readable, but migrate them to the
    # canonical key when that key is still free. This prevents WhatsApp and
    # business-operation records from creating two customers for one phone.
    if row.identity_key != key:
        key_owner = (
            db.query(CustomerRecord)
            .filter(
                CustomerRecord.company_id == company_id,
                CustomerRecord.identity_key == key,
                CustomerRecord.id != row.id,
            )
            .first()
        )
        if key_owner is None:
            row.identity_key = key

    if clean(name) and not row.name:
        row.name = clean(name)
    if normalized_phone:
        row.phone = normalized_phone
    if clean(email):
        row.email = clean(email)
    if normalized_external:
        row.external_contact_id = normalized_external
    if normalized_channel:
        row.channel = normalized_channel
    if now and (row.last_seen_at is None or now > row.last_seen_at):
        row.last_seen_at = now
    return row


def ensure_event(
    db,
    company_id: int,
    key: str,
    event_type: str,
    title: str,
    *,
    message=None,
    severity="info",
    payload=None,
    created_at=None,
):
    existing = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.company_id == company_id,
            NotificationEvent.event_key == key,
        )
        .first()
    )
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
        created_at=created_at or utcnow_naive(),
    )
    db.add(row)
    return row


def sync_company(db, company_id: int) -> None:
    for lead in db.query(Lead).filter(Lead.company_id == company_id).all():
        upsert_customer(
            db,
            company_id,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            seen_at=lead.created_at,
        )
        ensure_event(
            db,
            company_id,
            f"lead:{lead.id}",
            "lead_new",
            "New lead",
            message=lead.name or lead.interest,
            payload={"lead_id": lead.id},
            created_at=lead.created_at,
        )

    for booking in db.query(Booking).filter(Booking.company_id == company_id).all():
        upsert_customer(
            db,
            company_id,
            name=booking.customer_name,
            phone=booking.phone,
            seen_at=booking.created_at,
        )
        ensure_event(
            db,
            company_id,
            f"booking:{booking.id}",
            "booking_new",
            "New booking",
            message=booking.customer_name or booking.service,
            payload={"booking_id": booking.id},
            created_at=booking.created_at,
        )

    for order in db.query(Order).filter(Order.company_id == company_id).all():
        upsert_customer(
            db,
            company_id,
            name=order.customer_name,
            phone=order.phone,
            seen_at=order.created_at,
        )
        ensure_event(
            db,
            company_id,
            f"order:{order.id}",
            "order_new",
            "New order",
            message=order.customer_name,
            payload={"order_id": order.id},
            created_at=order.created_at,
        )

    for conversation in (
        db.query(AIConversation)
        .filter(AIConversation.company_id == company_id)
        .all()
    ):
        if conversation.external_contact_id:
            upsert_customer(
                db,
                company_id,
                external=conversation.external_contact_id,
                channel=conversation.channel_type,
                seen_at=conversation.created_at,
            )

    for handoff in (
        db.query(HumanHandoff)
        .filter(
            HumanHandoff.company_id == company_id,
            HumanHandoff.status == "pending",
        )
        .all()
    ):
        ensure_event(
            db,
            company_id,
            f"handoff:{handoff.id}",
            "handoff_pending",
            "Human handoff waiting",
            message=handoff.reason,
            severity="warning",
            payload={
                "handoff_id": handoff.id,
                "conversation_id": handoff.conversation_id,
            },
            created_at=handoff.created_at,
        )

    attention_states = ["external_failed", "executing", "cancelling", "pending_human"]
    for request in (
        db.query(ActionRequest)
        .filter(
            ActionRequest.company_id == company_id,
            ActionRequest.status.in_(attention_states),
        )
        .all()
    ):
        ensure_event(
            db,
            company_id,
            f"operation:{request.id}:{request.status}",
            "operation_attention",
            "Operation needs attention",
            message=request.summary or request.action_type,
            severity="warning",
            payload={"request_id": request.id, "status": request.status},
            created_at=request.created_at,
        )

    for usage in (
        db.query(AIUsage)
        .filter(AIUsage.company_id == company_id, AIUsage.status == "failed")
        .all()
    ):
        ensure_event(
            db,
            company_id,
            f"ai-failure:{usage.id}",
            "ai_failure",
            "AI request failed",
            message=usage.error_message,
            severity="critical",
            payload={"usage_id": usage.id, "agent_id": usage.agent_id},
            created_at=usage.created_at,
        )

    pref = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.company_id == company_id)
        .first()
    )
    if pref is None:
        db.add(
            NotificationPreference(
                company_id=company_id,
                event_types=list(DEFAULT_EVENTS),
                destinations=["dashboard"],
            )
        )
    db.flush()


def customer_metrics(db, company_id: int, customer: CustomerRecord) -> dict:
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
        conversation_count = (
            db.query(func.count(AIConversation.id))
            .filter(
                AIConversation.company_id == company_id,
                AIConversation.external_contact_id == customer.external_contact_id,
            )
            .scalar()
            or 0
        )
    return {
        "leads": leads.count(),
        "bookings": bookings.count(),
        "orders": orders.count(),
        "conversations": int(conversation_count),
    }


def list_customers(db, company_id: int) -> list[dict]:
    sync_company(db, company_id)
    db.commit()
    rows = (
        db.query(CustomerRecord)
        .filter(CustomerRecord.company_id == company_id)
        .order_by(CustomerRecord.last_seen_at.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "phone": row.phone,
            "email": row.email,
            "external_contact_id": row.external_contact_id,
            "channel": row.channel,
            "tags": row.tags or [],
            "notes": row.notes,
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
            "metrics": customer_metrics(db, company_id, row),
        }
        for row in rows
    ]


def customer_detail(db, company_id: int, customer_id: int) -> dict | None:
    sync_company(db, company_id)
    db.commit()
    row = (
        db.query(CustomerRecord)
        .filter(
            CustomerRecord.company_id == company_id,
            CustomerRecord.id == customer_id,
        )
        .first()
    )
    if row is None:
        return None

    phone, email = row.phone, row.email
    if phone:
        leads = (
            db.query(Lead)
            .filter(Lead.company_id == company_id, Lead.phone == phone)
            .order_by(Lead.created_at.desc())
            .all()
        )
        bookings = (
            db.query(Booking)
            .filter(Booking.company_id == company_id, Booking.phone == phone)
            .order_by(Booking.created_at.desc())
            .all()
        )
        orders = (
            db.query(Order)
            .filter(Order.company_id == company_id, Order.phone == phone)
            .order_by(Order.created_at.desc())
            .all()
        )
    elif email:
        leads = (
            db.query(Lead)
            .filter(Lead.company_id == company_id, Lead.email == email)
            .order_by(Lead.created_at.desc())
            .all()
        )
        bookings = []
        orders = []
    else:
        leads = []
        bookings = []
        orders = []

    conversations = []
    if row.external_contact_id:
        conversations = (
            db.query(AIConversation)
            .filter(
                AIConversation.company_id == company_id,
                AIConversation.external_contact_id == row.external_contact_id,
            )
            .order_by(AIConversation.created_at.desc())
            .all()
        )

    return {
        "customer": {
            "id": row.id,
            "name": row.name,
            "phone": row.phone,
            "email": row.email,
            "channel": row.channel,
            "tags": row.tags or [],
            "notes": row.notes,
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
        },
        "leads": [
            {
                "id": item.id,
                "interest": item.interest,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in leads
        ],
        "bookings": [
            {
                "id": item.id,
                "service": item.service,
                "date": item.booking_date,
                "time": item.booking_time,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in bookings
        ],
        "orders": [
            {
                "id": item.id,
                "items": item.items,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in orders
        ],
        "conversations": [
            {
                "id": item.id,
                "agent_id": item.agent_id,
                "channel": item.channel_type,
                "title": item.title,
                "created_at": item.created_at,
            }
            for item in conversations
        ],
    }


def update_customer(
    db,
    company_id: int,
    customer_id: int,
    *,
    name=None,
    phone=None,
    email=None,
    tags=None,
    notes=None,
) -> CustomerRecord | None:
    row = (
        db.query(CustomerRecord)
        .filter(
            CustomerRecord.company_id == company_id,
            CustomerRecord.id == customer_id,
        )
        .first()
    )
    if row is None:
        return None

    new_phone = normalize_phone(phone)
    new_email = clean(email)
    new_key = identity_key(
        phone=new_phone,
        email=new_email,
        external=row.external_contact_id,
        channel=row.channel,
    )
    if new_key and new_key != row.identity_key:
        conflict = (
            db.query(CustomerRecord)
            .filter(
                CustomerRecord.company_id == company_id,
                CustomerRecord.identity_key == new_key,
                CustomerRecord.id != row.id,
            )
            .first()
        )
        if conflict is not None:
            raise ValueError("A customer with that phone/email already exists")
        row.identity_key = new_key

    row.name = clean(name)
    row.phone = new_phone
    row.email = new_email
    row.tags = sorted(set(x.strip() for x in (tags or []) if x and x.strip()))
    row.notes = clean(notes)
    db.commit()
    db.refresh(row)
    return row


def notification_feed(db, company_id: int) -> dict:
    sync_company(db, company_id)
    db.commit()
    pref = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.company_id == company_id)
        .first()
    )
    enabled_types = set(pref.event_types or DEFAULT_EVENTS) if pref and pref.enabled else set()
    rows = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.company_id == company_id)
        .order_by(NotificationEvent.created_at.desc())
        .limit(200)
        .all()
    )
    rows = [item for item in rows if item.event_type in enabled_types]
    destinations = [
        item
        for item in (pref.destinations or ["dashboard"] if pref else ["dashboard"])
        if item in SUPPORTED_NOTIFICATION_DESTINATIONS
    ]
    return {
        "unread": sum(1 for item in rows if not item.read),
        "available_destinations": sorted(SUPPORTED_NOTIFICATION_DESTINATIONS),
        "preferences": (
            {
                "enabled": pref.enabled,
                "event_types": pref.event_types or [],
                "destinations": destinations or ["dashboard"],
            }
            if pref
            else None
        ),
        "events": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "severity": item.severity,
                "title": item.title,
                "message": item.message,
                "payload": item.payload or {},
                "read": item.read,
                "created_at": item.created_at,
            }
            for item in rows
        ],
    }


def update_notification_preferences(
    db,
    company_id: int,
    *,
    enabled: bool,
    event_types: list[str],
    destinations: list[str],
) -> NotificationPreference:
    row = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.company_id == company_id)
        .first()
    )
    if row is None:
        row = NotificationPreference(company_id=company_id)
        db.add(row)
    row.enabled = enabled
    row.event_types = [item for item in event_types if item in DEFAULT_EVENTS]
    row.destinations = [
        item for item in destinations if item in SUPPORTED_NOTIFICATION_DESTINATIONS
    ] or ["dashboard"]
    # External notification delivery is not implemented yet. Clear legacy
    # destinations instead of presenting a setting that cannot execute.
    row.email = None
    row.whatsapp = None
    row.webhook_url = None
    db.commit()
    db.refresh(row)
    return row


def mark_all_notifications_read(db, company_id: int) -> int:
    updated = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.company_id == company_id,
            NotificationEvent.read.is_(False),
        )
        .update({NotificationEvent.read: True}, synchronize_session=False)
    )
    db.commit()
    return int(updated or 0)


def business_analytics(db, company_id: int, days: int = 30) -> dict:
    safe_days = max(1, min(int(days), 365))
    since = utcnow_naive() - timedelta(days=safe_days)
    conversations = (
        db.query(AIConversation)
        .filter(
            AIConversation.company_id == company_id,
            AIConversation.created_at >= since,
        )
        .all()
    )
    bookings = (
        db.query(Booking)
        .filter(Booking.company_id == company_id, Booking.created_at >= since)
        .all()
    )
    orders = (
        db.query(Order)
        .filter(Order.company_id == company_id, Order.created_at >= since)
        .all()
    )
    leads = (
        db.query(Lead)
        .filter(Lead.company_id == company_id, Lead.created_at >= since)
        .all()
    )
    handoffs = (
        db.query(HumanHandoff)
        .filter(HumanHandoff.company_id == company_id, HumanHandoff.created_at >= since)
        .all()
    )
    usage = (
        db.query(AIUsage)
        .filter(AIUsage.company_id == company_id, AIUsage.created_at >= since)
        .all()
    )
    operations = (
        db.query(ActionRequest)
        .filter(ActionRequest.company_id == company_id, ActionRequest.created_at >= since)
        .all()
    )

    completed_ops = sum(1 for item in operations if item.status == "completed")
    conversion_base = len(conversations) or 1
    conversion_events = len(bookings) + len(orders) + len(leads)
    by_channel = Counter((item.channel_type or "internal") for item in conversations)
    by_agent = Counter(item.agent_id for item in conversations)
    agent_names = {
        item.id: item.name
        for item in db.query(AIAgent).filter(AIAgent.company_id == company_id).all()
    }
    daily = defaultdict(
        lambda: {"conversations": 0, "bookings": 0, "orders": 0, "leads": 0}
    )
    for item in conversations:
        daily[item.created_at.date().isoformat()]["conversations"] += 1
    for item in bookings:
        daily[item.created_at.date().isoformat()]["bookings"] += 1
    for item in orders:
        daily[item.created_at.date().isoformat()]["orders"] += 1
    for item in leads:
        daily[item.created_at.date().isoformat()]["leads"] += 1

    total_cost = sum((Decimal(item.provider_cost or 0) for item in usage), Decimal("0"))
    total_tokens = sum(int(item.total_tokens or 0) for item in usage)
    failures = sum(1 for item in usage if item.status == "failed")
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
        "channels": [
            {"channel": key, "conversations": value}
            for key, value in by_channel.most_common()
        ],
        "agents": [
            {
                "agent_id": key,
                "name": agent_names.get(key, f"AI Employee #{key}"),
                "conversations": value,
            }
            for key, value in by_agent.most_common()
        ],
        "daily": [
            {"date": key, **value}
            for key, value in sorted(daily.items())
        ],
    }
