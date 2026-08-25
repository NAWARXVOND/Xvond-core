import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from redis.exceptions import RedisError

from backend.app.core.config_secrets import reveal_config
from backend.app.models.company_module import CompanyModule
from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.audit.service import audit_service
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.handoff import activate_human_handoff, echo_recipient, extend_human_handoff, human_handoff_active, requests_human
from backend.app.modules.channels.whatsapp import whatsapp_sender
from backend.app.modules.channels.whatsapp_models import WhatsAppInboundMessage, WhatsAppSession
from backend.app.modules.channels.whatsapp_queue import whatsapp_job_queue

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhook"])


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


def process_business_app_echo(db, channel: AgentChannel, value: dict) -> list[dict]:
    processed = []
    for echo in value.get("message_echoes", []) or []:
        wa_id = echo_recipient(echo)
        message_id = str(echo.get("id") or "")
        if not wa_id:
            continue
        session = (
            db.query(WhatsAppSession)
            .filter(
                WhatsAppSession.company_id == channel.company_id,
                WhatsAppSession.agent_id == channel.agent_id,
                WhatsAppSession.phone_number_id == str(value.get("metadata", {}).get("phone_number_id", "")),
                WhatsAppSession.wa_id == wa_id,
            )
            .first()
        )
        if session is None:
            processed.append({"message_id": message_id, "status": "human_echo_without_session"})
            continue
        activate_human_handoff(session, reason="business_app_reply", human_message=True)
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
            },
        )
        processed.append({"message_id": message_id, "conversation_id": session.conversation_id, "status": "human_active"})
    return processed


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
                    db.commit()
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

                        if requests_human(incoming_text):
                            activate_human_handoff(session, reason="customer_request")
                            send_result = whatsapp_sender.send_text(
                                config=config,
                                to=wa_id,
                                text="تم تحويل المحادثة إلى موظف. سيتم الرد عليك من واتساب بزنس.",
                            )
                            if not send_result.get("success"):
                                db.rollback()
                                release_message_claim(db, message_id)
                                raise RuntimeError("WhatsApp handoff acknowledgement delivery failed")
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
