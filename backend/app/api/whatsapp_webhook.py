import hashlib
import hmac
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from redis.exceptions import RedisError

from backend.app.core.config_secrets import reveal_config
from backend.app.core.customer_runtime_policy import (
    human_handoff_acknowledgement,
    is_service_access_error,
    safe_service_unavailable_message,
)
from backend.app.models.company_module import CompanyModule
from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.ai_agent.models import AIMessage
from backend.app.modules.audit.service import audit_service
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.handoff import activate_human_handoff, echo_recipient, extend_human_handoff, human_handoff_active, requests_human
from backend.app.modules.channels.whatsapp import whatsapp_sender
from backend.app.modules.channels.whatsapp_models import WhatsAppInboundMessage, WhatsAppSession
from backend.app.modules.channels.whatsapp_queue import whatsapp_job_queue
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhook"])
ACTIVE_HANDOFF_STATUSES = ["pending", "in_progress"]


def get_whatsapp_channels(db):
    return (
        db.query(AgentChannel)
        .join(CompanyModule, CompanyModule.company_id == AgentChannel.company_id)
        .filter(
            AgentChannel.channel_type == "whatsapp",
            AgentChannel.enabled.is_(True),
            CompanyModule.module_name == "channels",
            CompanyModule.enabled.is_(True),
        )
        .all()
    )


def find_channel_by_phone_number_id(db, phone_number_id: str):
    return next(
        (
            channel
            for channel in get_whatsapp_channels(db)
            if str(reveal_config(channel.config).get("phone_number_id", "")) == str(phone_number_id)
        ),
        None,
    )


def verify_signature(raw_body: bytes, signature: str | None, app_secret: str | None):
    if not app_secret or not signature:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def claim_message(db, message_id: str, company_id: int, agent_id: int, wa_id: str) -> bool:
    item = WhatsAppInboundMessage(
        external_message_id=message_id,
        company_id=company_id,
        agent_id=agent_id,
        wa_id=wa_id,
    )
    db.add(item)
    try:
        # Persist only the idempotency claim before processing. Business actions
        # happen in the next transaction and commit only after reply delivery.
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def release_message_claim(db, message_id: str):
    item = db.query(WhatsAppInboundMessage).filter(WhatsAppInboundMessage.external_message_id == message_id).first()
    if item is not None:
        db.delete(item)
    db.commit()


def lock_contact(db, agent_id: int, wa_id: str):
    key = f"xvond-whatsapp:{agent_id}:{wa_id}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def _ensure_handoff_record(db, *, channel: AgentChannel, conversation_id: int, reason: str, status: str = "pending"):
    row = (
        db.query(HumanHandoff)
        .filter(
            HumanHandoff.company_id == channel.company_id,
            HumanHandoff.conversation_id == conversation_id,
            HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES),
        )
        .order_by(HumanHandoff.id.desc())
        .first()
    )
    if row is None:
        row = HumanHandoff(
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            conversation_id=conversation_id,
            reason=reason,
            priority="high" if reason == "service_limit_or_entitlement" else "normal",
            department="customer_service",
            status=status,
        )
        db.add(row)
    else:
        row.reason = reason or row.reason
        if row.status == "pending" and status == "in_progress":
            row.status = "in_progress"
    return row


def _business_app_echo_content(echo: dict) -> str:
    message_type = str(echo.get("type") or "unknown").strip().lower()
    payload = echo.get(message_type) or {}

    if message_type == "text":
        body = str((echo.get("text") or {}).get("body") or "").strip()
        return body or "[Empty WhatsApp Business message]"

    if isinstance(payload, dict):
        caption = str(payload.get("caption") or "").strip()
        if caption:
            return caption

    labels = {
        "image": "[Image sent from WhatsApp Business]",
        "video": "[Video sent from WhatsApp Business]",
        "audio": "[Audio sent from WhatsApp Business]",
        "voice": "[Voice message sent from WhatsApp Business]",
        "document": "[Document sent from WhatsApp Business]",
        "sticker": "[Sticker sent from WhatsApp Business]",
        "location": "[Location sent from WhatsApp Business]",
        "contacts": "[Contact shared from WhatsApp Business]",
        "contact": "[Contact shared from WhatsApp Business]",
        "reaction": "[Reaction sent from WhatsApp Business]",
        "edit": "[Message edited in WhatsApp Business]",
        "revoke": "[Message deleted in WhatsApp Business]",
    }
    return labels.get(message_type, f"[{message_type or 'Message'} sent from WhatsApp Business]")


def _business_app_echo_created_at(echo: dict) -> datetime | None:
    timestamp = str(echo.get("timestamp") or "").strip()
    if not timestamp:
        return None
    try:
        return datetime.utcfromtimestamp(int(timestamp))
    except (TypeError, ValueError, OverflowError):
        return None


def process_business_app_echo(db, channel: AgentChannel, value: dict) -> list[dict]:
    """Mirror WhatsApp Business App replies into the Xvond conversation inbox.

    smb_message_echoes are emitted by Meta Coexistence when a staff member
    sends from the WhatsApp Business app or a linked device. Every echo is
    deduplicated by its WhatsApp message id, recorded in the same conversation,
    and places that conversation under explicit human control.
    """
    processed = []
    phone_number_id = str((value.get("metadata") or {}).get("phone_number_id") or "")

    for echo in value.get("message_echoes", []) or []:
        wa_id = echo_recipient(echo)
        message_id = str(echo.get("id") or "").strip()
        if not wa_id or not message_id:
            processed.append({"message_id": message_id, "status": "ignored_invalid_echo"})
            continue

        claimed = claim_message(
            db=db,
            message_id=message_id,
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            wa_id=wa_id,
        )
        if not claimed:
            processed.append({"message_id": message_id, "status": "duplicate"})
            continue

        content = _business_app_echo_content(echo)

        try:
            lock_contact(db, channel.agent_id, wa_id)
            session = (
                db.query(WhatsAppSession)
                .filter(
                    WhatsAppSession.company_id == channel.company_id,
                    WhatsAppSession.agent_id == channel.agent_id,
                    WhatsAppSession.phone_number_id == phone_number_id,
                    WhatsAppSession.wa_id == wa_id,
                )
                .first()
            )
            if session is None:
                session = _get_or_create_whatsapp_session(
                    db=db,
                    channel=channel,
                    wa_id=wa_id,
                    phone_number_id=phone_number_id,
                    incoming_text=content,
                )

            activate_human_handoff(session, reason="business_app_reply", human_message=True)
            _ensure_handoff_record(
                db,
                channel=channel,
                conversation_id=session.conversation_id,
                reason="business_app_reply",
                status="in_progress",
            )

            message_kwargs = {
                "conversation_id": session.conversation_id,
                "role": "human",
                "content": content,
            }
            created_at = _business_app_echo_created_at(echo)
            if created_at is not None:
                message_kwargs["created_at"] = created_at
            db.add(AIMessage(**message_kwargs))

            audit_service.log(
                db=db,
                company_id=channel.company_id,
                action="whatsapp.human_reply_detected",
                resource_type="channel",
                resource_id=channel.id,
                details={
                    "message_id": message_id,
                    "conversation_id": session.conversation_id,
                    "wa_id": wa_id,
                    "source": "whatsapp_business_app",
                    "message_type": str(echo.get("type") or "unknown"),
                    "mirrored_to_inbox": True,
                },
            )
            db.commit()
            processed.append({
                "message_id": message_id,
                "conversation_id": session.conversation_id,
                "status": "human_active",
                "mirrored": True,
            })
        except Exception:
            db.rollback()
            release_message_claim(db, message_id)
            raise

    return processed


def _get_or_create_whatsapp_session(db, channel: AgentChannel, wa_id: str, phone_number_id: str, incoming_text: str):
    session = (
        db.query(WhatsAppSession)
        .filter(WhatsAppSession.agent_id == channel.agent_id, WhatsAppSession.wa_id == wa_id)
        .first()
    )
    if session is None:
        conversation = agent_runtime.get_or_create_conversation(
            db=db,
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            conversation_id=None,
            message=incoming_text,
        )
        session = WhatsAppSession(
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            conversation_id=conversation.id,
            wa_id=wa_id,
            phone_number_id=phone_number_id,
        )
        db.add(session)
        db.flush()
    return session


def _service_access_fallback(db, *, channel: AgentChannel, config: dict, wa_id: str, phone_number_id: str, incoming_text: str, message_id: str, error: HTTPException):
    db.rollback()
    lock_contact(db, channel.agent_id, wa_id)
    session = _get_or_create_whatsapp_session(db, channel, wa_id, phone_number_id, incoming_text)
    agent = agent_runtime.get_agent(db, channel.company_id, channel.agent_id)
    activate_human_handoff(session, reason="service_limit_or_entitlement")
    _ensure_handoff_record(
        db,
        channel=channel,
        conversation_id=session.conversation_id,
        reason="service_limit_or_entitlement",
    )
    reply_text = safe_service_unavailable_message(agent.system_prompt or "", incoming_text)
    db.add(AIMessage(conversation_id=session.conversation_id, role="user", content=incoming_text))
    db.add(AIMessage(conversation_id=session.conversation_id, role="assistant", content=reply_text))
    send_result = whatsapp_sender.send_text(config=config, to=wa_id, text=reply_text)
    if not send_result.get("success"):
        db.rollback()
        release_message_claim(db, message_id)
        raise RuntimeError("WhatsApp service fallback delivery failed")
    audit_service.log(
        db=db,
        company_id=channel.company_id,
        action="whatsapp.customer_service_fallback",
        resource_type="channel",
        resource_id=channel.id,
        details={
            "message_id": message_id,
            "conversation_id": session.conversation_id,
            "internal_status": error.status_code,
            "internal_detail": error.detail,
        },
    )
    db.commit()
    return session.conversation_id


@router.get("")
def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    db = SessionLocal()
    try:
        if mode != "subscribe":
            raise HTTPException(status_code=403, detail="Invalid webhook mode")
        if not verify_token:
            raise HTTPException(status_code=403, detail="Verify token required")
        for channel in get_whatsapp_channels(db):
            config = reveal_config(channel.config)
            stored_token = str(config.get("verify_token", ""))
            if stored_token and hmac.compare_digest(stored_token, str(verify_token)):
                return int(challenge or "0")
        raise HTTPException(status_code=403, detail="Invalid verify token")
    finally:
        db.close()


def validate_webhook_request(raw_body: bytes, signature: str | None) -> tuple[dict, int]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=400, detail="Invalid WhatsApp webhook object")
    db = SessionLocal()
    matched_channels = 0
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {}) or {}
                metadata = value.get("metadata", {}) or {}
                phone_number_id = str(metadata.get("phone_number_id", ""))
                if not phone_number_id:
                    continue
                channel = find_channel_by_phone_number_id(db, phone_number_id)
                if channel is None:
                    continue
                matched_channels += 1
                config = reveal_config(channel.config)
                if not verify_signature(raw_body, signature, config.get("app_secret")):
                    raise HTTPException(status_code=403, detail="Invalid webhook signature")
    finally:
        db.close()
    return payload, matched_channels


@router.post("")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    _, matched_channels = validate_webhook_request(raw_body=raw_body, signature=signature)
    if matched_channels == 0:
        return {"status": "ignored", "reason": "unknown_phone_number_id"}
    if whatsapp_job_queue.enabled:
        try:
            job_id = whatsapp_job_queue.enqueue(body=raw_body.decode("utf-8"), signature=signature or "")
        except (RedisError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="WhatsApp processing queue unavailable") from exc
        return {"status": "accepted", "job_id": job_id}
    return process_webhook_payload(raw_body=raw_body, signature=signature)


def process_webhook_payload(raw_body: bytes, signature: str | None):
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=400, detail="Invalid WhatsApp webhook object")

    db = SessionLocal()
    processed = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {}) or {}
                metadata = value.get("metadata", {}) or {}
                phone_number_id = str(metadata.get("phone_number_id", ""))
                if not phone_number_id:
                    continue
                channel = find_channel_by_phone_number_id(db, phone_number_id)
                if channel is None:
                    continue
                config = reveal_config(channel.config)
                if not verify_signature(raw_body, signature, config.get("app_secret")):
                    raise HTTPException(status_code=403, detail="Invalid webhook signature")

                field = change.get("field")
                if field == "smb_message_echoes":
                    processed.extend(process_business_app_echo(db=db, channel=channel, value=value))
                    continue
                if field not in (None, "messages"):
                    continue

                for message in value.get("messages", []):
                    message_id = message.get("id")
                    wa_id = message.get("from")
                    if not message_id or not wa_id:
                        continue
                    claimed = claim_message(
                        db=db,
                        message_id=message_id,
                        company_id=channel.company_id,
                        agent_id=channel.agent_id,
                        wa_id=wa_id,
                    )
                    if not claimed:
                        processed.append({"message_id": message_id, "status": "duplicate"})
                        continue

                    if message.get("type") != "text":
                        processed.append({"message_id": message_id, "status": "ignored_non_text"})
                        continue
                    incoming_text = str((message.get("text", {}) or {}).get("body", "")).strip()
                    if not incoming_text:
                        processed.append({"message_id": message_id, "status": "ignored_empty"})
                        continue

                    try:
                        lock_contact(db, channel.agent_id, wa_id)
                        session = _get_or_create_whatsapp_session(db, channel, wa_id, phone_number_id, incoming_text)
                        agent = agent_runtime.get_agent(db, channel.company_id, channel.agent_id)

                        if requests_human(incoming_text):
                            activate_human_handoff(session, reason="customer_request")
                            _ensure_handoff_record(
                                db,
                                channel=channel,
                                conversation_id=session.conversation_id,
                                reason="customer_request",
                            )
                            send_result = whatsapp_sender.send_text(
                                config=config,
                                to=wa_id,
                                text=human_handoff_acknowledgement(agent.system_prompt or "", incoming_text),
                            )
                            if not send_result.get("success"):
                                db.rollback()
                                release_message_claim(db, message_id)
                                raise RuntimeError("WhatsApp handoff acknowledgement delivery failed")
                            db.add(AIMessage(conversation_id=session.conversation_id, role="user", content=incoming_text))
                            audit_service.log(
                                db=db,
                                company_id=channel.company_id,
                                action="whatsapp.handoff_requested",
                                resource_type="channel",
                                resource_id=channel.id,
                                details={
                                    "message_id": message_id,
                                    "conversation_id": session.conversation_id,
                                    "acknowledgement_sent": True,
                                },
                            )
                            db.commit()
                            processed.append({"message_id": message_id, "conversation_id": session.conversation_id, "status": "waiting_for_human"})
                            continue

                        if human_handoff_active(session):
                            extend_human_handoff(session)
                            _ensure_handoff_record(
                                db,
                                channel=channel,
                                conversation_id=session.conversation_id,
                                reason=session.handoff_reason or "human_active",
                            )
                            db.add(AIMessage(conversation_id=session.conversation_id, role="user", content=incoming_text))
                            audit_service.log(
                                db=db,
                                company_id=channel.company_id,
                                action="whatsapp.message_routed_to_human",
                                resource_type="channel",
                                resource_id=channel.id,
                                details={"message_id": message_id, "conversation_id": session.conversation_id, "wa_id": wa_id},
                            )
                            db.commit()
                            processed.append({"message_id": message_id, "conversation_id": session.conversation_id, "status": "waiting_for_human"})
                            continue

                        # Keep the complete conversation + business action transaction open.
                        # It is committed only after WhatsApp confirms the outgoing API call.
                        result = agent_runtime.chat(
                            db=db,
                            company_id=channel.company_id,
                            agent_id=channel.agent_id,
                            message=incoming_text,
                            conversation_id=session.conversation_id,
                            commit=False,
                        )
                    except HTTPException as exc:
                        if is_service_access_error(exc):
                            conversation_id = _service_access_fallback(
                                db,
                                channel=channel,
                                config=config,
                                wa_id=wa_id,
                                phone_number_id=phone_number_id,
                                incoming_text=incoming_text,
                                message_id=message_id,
                                error=exc,
                            )
                            processed.append({"message_id": message_id, "conversation_id": conversation_id, "status": "waiting_for_human"})
                            continue
                        db.rollback()
                        release_message_claim(db, message_id)
                        audit_service.log(
                            db=db,
                            company_id=channel.company_id,
                            action="whatsapp.runtime_failed",
                            resource_type="channel",
                            resource_id=channel.id,
                            details={"message_id": message_id, "error": str(exc)[:1000]},
                        )
                        db.commit()
                        raise
                    except Exception as exc:
                        db.rollback()
                        release_message_claim(db, message_id)
                        audit_service.log(
                            db=db,
                            company_id=channel.company_id,
                            action="whatsapp.runtime_failed",
                            resource_type="channel",
                            resource_id=channel.id,
                            details={"message_id": message_id, "error": str(exc)[:1000]},
                        )
                        db.commit()
                        raise

                    reply_text = str(result["response"]["content"])
                    send_result = whatsapp_sender.send_text(config=config, to=wa_id, text=reply_text)
                    if not send_result.get("success"):
                        # Roll back the assistant/user messages AND every booking/order/lead
                        # made by this turn. Release the claim so the worker can retry safely.
                        db.rollback()
                        release_message_claim(db, message_id)
                        audit_service.log(
                            db=db,
                            company_id=channel.company_id,
                            action="whatsapp.reply_retry_scheduled",
                            resource_type="channel",
                            resource_id=channel.id,
                            details={
                                "message_id": message_id,
                                "status_code": send_result.get("status_code"),
                                "error": str(send_result.get("error", ""))[:1000],
                            },
                        )
                        db.commit()
                        raise RuntimeError("WhatsApp reply delivery failed")

                    audit_service.log(
                        db=db,
                        company_id=channel.company_id,
                        action="whatsapp.reply_sent",
                        resource_type="channel",
                        resource_id=channel.id,
                        details={
                            "message_id": message_id,
                            "conversation_id": result["conversation_id"],
                            "success": True,
                            "status_code": send_result.get("status_code"),
                        },
                    )
                    db.commit()
                    processed.append({
                        "message_id": message_id,
                        "agent_id": channel.agent_id,
                        "conversation_id": result["conversation_id"],
                        "reply_sent": True,
                    })
        return {"status": "ok", "processed": processed}
    finally:
        db.close()
