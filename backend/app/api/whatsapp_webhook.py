import hashlib
import hmac
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool

from backend.app.api.admin_meta_whatsapp import _meta_settings
from backend.app.core.config_secrets import reveal_config, merge_config
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
from backend.app.modules.channels.conversation_source import bind_conversation_source
from backend.app.modules.channels.handoff import activate_human_handoff, echo_recipient, extend_human_handoff, human_handoff_active, requests_human
from backend.app.modules.channels.whatsapp import whatsapp_sender
from backend.app.modules.channels.whatsapp_models import WhatsAppInboundMessage, WhatsAppSession
from backend.app.modules.channels.whatsapp_queue import whatsapp_job_queue
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhook"])
ACTIVE_HANDOFF_STATUSES = ["pending", "in_progress"]
logger = logging.getLogger(__name__)


def get_whatsapp_channels(db):
    return (
        db.query(AgentChannel)
        .join(CompanyModule, CompanyModule.company_id == AgentChannel.company_id)
        .filter(
            AgentChannel.channel_type == "whatsapp",
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
    try:
        # The claim and the processed event commit together. A worker crash must
        # not leave a permanent claim for an event that was never processed.
        with db.begin_nested():
            db.add(item)
            db.flush()
        return True
    except IntegrityError:
        return False


def release_message_claim(db, message_id: str):
    # Claims are transactional now. Never delete by external ID after rollback:
    # another worker may already have successfully processed that same event.
    db.rollback()


def lock_contact(db, agent_id: int, wa_id: str):
    key = f"xvond-whatsapp:{agent_id}:{wa_id}"
    if db.get_bind().dialect.name == "postgresql":
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


def _echo_precedes_explicit_ai_resume(
    session: WhatsAppSession,
    *,
    message_id: str,
    created_at: datetime | None,
) -> bool:
    resumed_at = session.ai_resumed_at
    if resumed_at is None:
        return False

    # Meta timestamps have one-second precision while our resume timestamp has
    # microseconds. Exact ingress identity resolves same-second ambiguity; older
    # whole-second echoes are safely stale.
    if session.ai_resume_echo_id and session.ai_resume_echo_id == message_id:
        return True
    if created_at is not None and created_at < resumed_at.replace(microsecond=0):
        return True
    return False


def process_business_app_echo(db, channel: AgentChannel, value: dict) -> list[dict]:
    """Mirror WhatsApp Business App replies into the Xvond conversation inbox.

    smb_message_echoes are emitted by Meta Coexistence when a staff member
    sends from the WhatsApp Business app or a linked device. Every echo is
    deduplicated by its WhatsApp message id and mirrored into the same
    conversation. A delayed echo that predates a newer explicit Return-to-AI is
    historical evidence only and must not reverse that operator decision.
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
            session = _get_or_create_whatsapp_session(
                db=db, channel=channel, wa_id=wa_id,
                phone_number_id=phone_number_id, incoming_text=content,
            )
            created_at = _business_app_echo_created_at(echo)
            stale_after_resume = _echo_precedes_explicit_ai_resume(
                session,
                message_id=message_id,
                created_at=created_at,
            )

            if not stale_after_resume:
                activate_human_handoff(
                    session,
                    reason="business_app_reply",
                    now=created_at,
                    human_message=True,
                )
                _ensure_handoff_record(
                    db,
                    channel=channel,
                    conversation_id=session.conversation_id,
                    reason="business_app_reply",
                    status="in_progress",
                )
            elif session.ai_resume_echo_id == message_id:
                # The exact delayed marker has now been consumed. The durable
                # resume timestamp continues protecting any older queued echoes.
                session.ai_resume_echo_id = None

            message_kwargs = {
                "conversation_id": session.conversation_id,
                "role": "human",
                "content": content,
            }
            if created_at is not None:
                message_kwargs["created_at"] = created_at
            db.add(AIMessage(**message_kwargs))
            config = reveal_config(channel.config) or {}
            if config.get("coexistence") is True:
                channel.config = merge_config(channel.config, {"coexistence_echo_received_at": datetime.utcnow().isoformat()})
                if config.get("activation_pending_coexistence"):
                    from backend.app.api.admin_channels import _activation_blockers
                    if not _activation_blockers(db, channel):
                        channel.enabled = True
                        channel.config = merge_config(channel.config, {"activation_pending_coexistence": False})

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
                    "human_control_activated": not stale_after_resume,
                    "stale_after_ai_resume": stale_after_resume,
                },
            )
            db.commit()
            processed.append({
                "message_id": message_id,
                "conversation_id": session.conversation_id,
                "status": "stale_echo_mirrored" if stale_after_resume else "human_active",
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
        .filter(
            WhatsAppSession.company_id == channel.company_id,
            WhatsAppSession.agent_id == channel.agent_id,
            WhatsAppSession.phone_number_id == phone_number_id,
            WhatsAppSession.wa_id == wa_id,
        )
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
    bind_conversation_source(
        db, conversation_id=session.conversation_id,
        company_id=channel.company_id, agent_id=channel.agent_id,
        channel_type="whatsapp", channel_id=channel.id, external_contact_id=wa_id,
    )
    return session


def _service_access_fallback(db, *, channel: AgentChannel, config: dict, wa_id: str, phone_number_id: str, incoming_text: str, message_id: str, error: HTTPException):
    db.rollback()
    lock_contact(db, channel.agent_id, wa_id)
    if not claim_message(db, message_id, channel.company_id, channel.agent_id, wa_id):
        raise RuntimeError("WhatsApp fallback event was already processed")
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
    if mode != "subscribe":
        raise HTTPException(status_code=403, detail="Invalid webhook mode")
    if not verify_token:
        raise HTTPException(status_code=403, detail="Verify token required")

    # Meta verifies the app callback before a customer WhatsApp channel may be
    # activated. Validate the platform-level token first so onboarding cannot
    # deadlock on an inactive/not-yet-created tenant channel.
    platform_token = str(_meta_settings().get("verify_token") or "")
    if platform_token and hmac.compare_digest(platform_token, str(verify_token)):
        return int(challenge or "0")

    # Keep tenant tokens as a backwards-compatible fallback for older channels.
    db = SessionLocal()
    try:
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
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=400, detail="Invalid WhatsApp webhook object")
    _validate_payload_shape(payload)
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


def _validate_payload_shape(payload):
    try:
        entries = payload.get("entry", [])
        if not isinstance(entries, list):
            raise ValueError
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("changes", []), list):
                raise ValueError
            for change in entry.get("changes", []):
                if not isinstance(change, dict):
                    raise ValueError
                value = change.get("value") or {}
                if not isinstance(value, dict) or not isinstance(value.get("metadata", {}), dict):
                    raise ValueError
                for key in ("messages", "message_echoes"):
                    messages = value.get(key, [])
                    if not isinstance(messages, list) or any(not isinstance(item, dict) for item in messages):
                        raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid WhatsApp webhook structure") from None


@router.post("")
async def receive_webhook(request: Request):
    raw_body = b""
    async for chunk in request.stream():
        raw_body += chunk
        if len(raw_body) > 1024 * 1024:
            raise HTTPException(413, "WhatsApp webhook payload is too large")
    signature = request.headers.get("x-hub-signature-256")
    payload, matched_channels = await run_in_threadpool(validate_webhook_request, raw_body=raw_body, signature=signature)
    if matched_channels == 0:
        return {"status": "ignored", "reason": "unknown_phone_number_id"}
    if whatsapp_job_queue.enabled:
        try:
            # Record the control signal at ingress, before a slow AI job can
            # finish. The worker still mirrors/deduplicates the signed echo.
            await run_in_threadpool(_mark_incoming_echoes, payload)
            job_id = whatsapp_job_queue.enqueue(body=raw_body.decode("utf-8"), signature=signature or "")
        except (RedisError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="WhatsApp processing queue unavailable") from exc
        return {"status": "accepted", "job_id": job_id}
    return await run_in_threadpool(process_webhook_payload, raw_body=raw_body, signature=signature)


def _mark_incoming_echoes(payload):
    db = SessionLocal()
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "smb_message_echoes":
                    continue
                value = change.get("value") or {}
                phone = str((value.get("metadata") or {}).get("phone_number_id") or "")
                if find_channel_by_phone_number_id(db, phone) is None:
                    continue
                for echo in value.get("message_echoes", []):
                    recipient, event_id = echo_recipient(echo), str(echo.get("id") or "")
                    if recipient and event_id and not db.query(WhatsAppInboundMessage.id).filter(WhatsAppInboundMessage.external_message_id == event_id).first():
                        whatsapp_job_queue.mark_human(phone, recipient, event_id)
    finally:
        db.close()


def process_webhook_payload(raw_body: bytes, signature: str | None):
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=400, detail="Invalid WhatsApp webhook object")
    _validate_payload_shape(payload)

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
                logger.info("WhatsApp event received; channel_id=%s field=%s", channel.id, field if field in {"messages", "smb_message_echoes", "smb_app_state_sync", "history", "account_update"} else "other")
                if field == "smb_message_echoes":
                    processed.extend(process_business_app_echo(db=db, channel=channel, value=value))
                    continue
                if field not in (None, "messages"):
                    continue
                if not channel.enabled:
                    logger.info("WhatsApp automation inactive; channel_id=%s", channel.id)
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
                        db.commit()
                        processed.append({"message_id": message_id, "status": "ignored_non_text"})
                        continue
                    incoming_text = str((message.get("text", {}) or {}).get("body", "")).strip()
                    if not incoming_text:
                        db.commit()
                        processed.append({"message_id": message_id, "status": "ignored_empty"})
                        continue

                    try:
                        lock_contact(db, channel.agent_id, wa_id)
                        session = _get_or_create_whatsapp_session(db, channel, wa_id, phone_number_id, incoming_text)
                        agent = agent_runtime.get_agent(db, channel.company_id, channel.agent_id)

                        if config.get("coexistence") is True:
                            from backend.app.modules.channels.whatsapp_connection import whatsapp_connection_state
                            if not whatsapp_connection_state(config).get("connected"):
                                activate_human_handoff(session, reason="coexistence_unverified")
                                logger.warning("WhatsApp automation held for unverified Coexistence; channel_id=%s", channel.id)

                        if whatsapp_job_queue.human_marker(phone_number_id, wa_id):
                            activate_human_handoff(session, reason="business_app_reply")

                        if requests_human(incoming_text) and not human_handoff_active(session):
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
                            details={"message_id": message_id, "error_type": type(exc).__name__},
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
                            details={"message_id": message_id, "error_type": type(exc).__name__},
                        )
                        db.commit()
                        raise

                    reply_text = str(result["response"]["content"])
                    # A portal takeover or signed echo may arrive while the
                    # provider is generating. Do not commit or deliver that turn.
                    db.refresh(session)
                    if human_handoff_active(session) or whatsapp_job_queue.human_marker(phone_number_id, wa_id):
                        db.rollback()
                        lock_contact(db, channel.agent_id, wa_id)
                        if claim_message(db, message_id, channel.company_id, channel.agent_id, wa_id):
                            session = _get_or_create_whatsapp_session(db, channel, wa_id, phone_number_id, incoming_text)
                            activate_human_handoff(session, reason="human_takeover_during_generation")
                            _ensure_handoff_record(db, channel=channel, conversation_id=session.conversation_id, reason=session.handoff_reason)
                            db.add(AIMessage(conversation_id=session.conversation_id, role="user", content=incoming_text))
                            db.commit()
                        processed.append({"message_id": message_id, "status": "waiting_for_human"})
                        continue
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
                                "error": "Meta delivery failed",
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
