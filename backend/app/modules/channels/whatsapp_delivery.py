from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from backend.app.modules.ai_agent.models import AIMessage
from backend.app.modules.channels.acceptance import mark_customer_roundtrip
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.whatsapp import whatsapp_sender
from backend.app.modules.channels.whatsapp_models import WhatsAppOutboundDelivery


SUCCESS_STATES = {"accepted", "delivered", "read"}
FINAL_STATES = SUCCESS_STATES | {"unknown"}


def _now() -> datetime:
    return datetime.utcnow()


def delivery_payload(row: WhatsAppOutboundDelivery) -> dict:
    return {
        "delivery_id": row.id,
        "status": row.status,
        "retryable": bool(row.retryable),
        "attempts": int(row.attempts or 0),
        "provider_message_id": row.provider_message_id,
        "status_code": row.last_status_code,
        "error_code": row.last_error_code,
    }


def ensure_delivery(
    db,
    *,
    idempotency_key: str,
    company_id: int,
    agent_id: int,
    conversation_id: int,
    channel_id: int,
    message_id: int,
    wa_id: str,
    inbound_external_message_id: str | None = None,
) -> WhatsAppOutboundDelivery:
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("WhatsApp delivery idempotency key is required")

    existing = (
        db.query(WhatsAppOutboundDelivery)
        .filter(WhatsAppOutboundDelivery.idempotency_key == key)
        .first()
    )
    if existing is not None:
        expected = (
            int(company_id),
            int(agent_id),
            int(conversation_id),
            int(channel_id),
            int(message_id),
            str(wa_id),
        )
        actual = (
            existing.company_id,
            existing.agent_id,
            existing.conversation_id,
            existing.channel_id,
            existing.message_id,
            existing.wa_id,
        )
        if actual != expected:
            raise RuntimeError("WhatsApp delivery idempotency key scope conflict")
        return existing

    row = WhatsAppOutboundDelivery(
        idempotency_key=key,
        company_id=company_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        channel_id=channel_id,
        message_id=message_id,
        inbound_external_message_id=inbound_external_message_id,
        wa_id=str(wa_id),
        status="pending",
        retryable=False,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        row = (
            db.query(WhatsAppOutboundDelivery)
            .filter(WhatsAppOutboundDelivery.idempotency_key == key)
            .first()
        )
        if row is None:
            raise
    return row


def _locked(db, delivery_id: int) -> WhatsAppOutboundDelivery:
    row = (
        db.query(WhatsAppOutboundDelivery)
        .filter(WhatsAppOutboundDelivery.id == delivery_id)
        .with_for_update()
        .first()
    )
    if row is None:
        raise RuntimeError("WhatsApp delivery record disappeared")
    return row


def _provider_id_conflicts(db, *, delivery_id: int, provider_message_id: str) -> bool:
    return (
        db.query(WhatsAppOutboundDelivery.id)
        .filter(
            WhatsAppOutboundDelivery.provider_message_id == provider_message_id,
            WhatsAppOutboundDelivery.id != delivery_id,
        )
        .first()
        is not None
    )


def attempt_delivery(db, *, delivery_id: int, config: dict) -> dict:
    """Send exactly one durable delivery attempt.

    The transition to ``sending`` is committed *before* the network call. If the
    process dies after Meta accepts the request but before Xvond records the
    provider message id, the next observer converts the row to ``unknown`` and
    does not blindly resend it. That trades a support/reconciliation event for
    avoiding duplicate customer messages and duplicate confirmations.
    """
    row = _locked(db, delivery_id)
    if row.status in SUCCESS_STATES:
        return {"success": True, "already_sent": True, **delivery_payload(row)}
    if row.status == "unknown":
        return {"success": False, "unknown": True, **delivery_payload(row)}
    if row.status == "sending":
        row.status = "unknown"
        row.retryable = False
        row.last_error_code = "interrupted_after_send_started"
        row.updated_at = _now()
        db.commit()
        return {"success": False, "unknown": True, **delivery_payload(row)}
    if row.status == "failed" and not row.retryable:
        return {"success": False, "permanent": True, **delivery_payload(row)}

    message = db.query(AIMessage).filter(AIMessage.id == row.message_id).first()
    if message is None or message.conversation_id != row.conversation_id:
        row.status = "failed"
        row.retryable = False
        row.last_error_code = "message_missing"
        row.failed_at = _now()
        db.commit()
        return {"success": False, "permanent": True, **delivery_payload(row)}

    row.status = "sending"
    row.retryable = False
    row.attempts = int(row.attempts or 0) + 1
    row.last_error_code = None
    row.last_status_code = None
    row.updated_at = _now()
    db.commit()

    result = whatsapp_sender.send_text(
        config=config,
        to=row.wa_id,
        text=message.content,
    )

    row = _locked(db, delivery_id)
    row.last_status_code = result.get("status_code")
    row.updated_at = _now()
    if result.get("success"):
        provider_message_id = (
            str(result.get("provider_message_id") or "").strip() or None
        )
        if provider_message_id and _provider_id_conflicts(
            db,
            delivery_id=row.id,
            provider_message_id=provider_message_id,
        ):
            # A provider message ID must identify one outbound delivery. If Meta
            # or an adapter ever returns the same ID for two deliveries, do not
            # crash the worker and do not guess which send is authoritative.
            row.provider_message_id = None
            row.status = "unknown"
            row.retryable = False
            row.last_error_code = "provider_message_id_conflict"
            db.commit()
            return {"success": False, "unknown": True, **delivery_payload(row)}

        row.provider_message_id = provider_message_id
        row.status = "accepted"
        row.retryable = False
        row.last_error_code = None
        row.accepted_at = _now()
        db.commit()
        return {"success": True, **delivery_payload(row)}

    certainty = str(result.get("delivery_certainty") or "unknown")
    if certainty == "rejected":
        row.status = "failed"
        row.retryable = bool(result.get("retryable"))
        row.last_error_code = str(
            result.get("error_type")
            or (
                f"http_{row.last_status_code}"
                if row.last_status_code
                else "meta_rejected"
            )
        )[:160]
        row.failed_at = _now()
    else:
        row.status = "unknown"
        row.retryable = False
        row.last_error_code = str(
            result.get("error_type") or "network_outcome_unknown"
        )[:160]
    db.commit()
    return {
        "success": False,
        "unknown": row.status == "unknown",
        "permanent": row.status == "failed" and not row.retryable,
        **delivery_payload(row),
    }


def delivery_for_inbound(db, inbound_external_message_id: str):
    return (
        db.query(WhatsAppOutboundDelivery)
        .filter(
            WhatsAppOutboundDelivery.inbound_external_message_id
            == str(inbound_external_message_id)
        )
        .order_by(WhatsAppOutboundDelivery.id.desc())
        .first()
    )


def retry_delivery_for_inbound(
    db,
    *,
    inbound_external_message_id: str,
    config: dict,
) -> dict | None:
    row = delivery_for_inbound(db, inbound_external_message_id)
    if row is None:
        return None
    if row.status in SUCCESS_STATES:
        return {"success": True, "already_sent": True, **delivery_payload(row)}
    if row.status == "unknown":
        return {"success": False, "unknown": True, **delivery_payload(row)}
    if row.status == "failed" and not row.retryable:
        return {"success": False, "permanent": True, **delivery_payload(row)}
    return attempt_delivery(db, delivery_id=row.id, config=config)


def apply_provider_status(
    db,
    status_event: dict,
) -> WhatsAppOutboundDelivery | None:
    provider_message_id = str(status_event.get("id") or "").strip()
    if not provider_message_id:
        return None
    row = (
        db.query(WhatsAppOutboundDelivery)
        .filter(
            WhatsAppOutboundDelivery.provider_message_id == provider_message_id
        )
        .with_for_update()
        .first()
    )
    if row is None:
        return None

    provider_status = str(status_event.get("status") or "").strip().lower()
    now = _now()
    if provider_status == "sent":
        if row.status not in {"delivered", "read"}:
            row.status = "accepted"
        row.accepted_at = row.accepted_at or now
        row.retryable = False
    elif provider_status == "delivered":
        if row.status != "read":
            row.status = "delivered"
        row.delivered_at = row.delivered_at or now
        row.accepted_at = row.accepted_at or now
        row.retryable = False
    elif provider_status == "read":
        row.status = "read"
        row.read_at = row.read_at or now
        row.delivered_at = row.delivered_at or now
        row.accepted_at = row.accepted_at or now
        row.retryable = False
    elif provider_status == "failed":
        row.status = "failed"
        row.retryable = False
        row.failed_at = now
        errors = status_event.get("errors") or []
        code = None
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            code = errors[0].get("code")
        row.last_error_code = (
            f"meta_status_{code}"[:160]
            if code is not None
            else "meta_status_failed"
        )
    else:
        return row

    if (
        row.status in {"delivered", "read"}
        and str(row.idempotency_key or "").endswith(":ai-reply-v1")
    ):
        channel = (
            db.query(AgentChannel)
            .filter(AgentChannel.id == row.channel_id)
            .first()
        )
        if channel is not None:
            mark_customer_roundtrip(
                channel,
                source="whatsapp_ai_delivery_confirmed",
            )

    row.updated_at = now
    db.flush()
    return row
