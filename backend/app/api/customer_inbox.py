from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_

from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.ai_agent.customer_access import can_view_conversations
from backend.app.modules.ai_agent.factory_models import AgentConfig
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage
from backend.app.modules.audit.service import audit_service
from backend.app.modules.channels.handoff import activate_human_handoff, human_handoff_active, resume_ai
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.whatsapp import whatsapp_sender
from backend.app.modules.channels.whatsapp_models import WhatsAppSession
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(prefix="/customer/inbox", tags=["Customer Conversation Inbox"])
ACTIVE_HANDOFF_STATUSES = {"pending", "in_progress"}


class HumanReply(BaseModel):
    message: str = Field(min_length=1, max_length=12000)


def _visible_agents(db, current_user: User) -> list[AIAgent]:
    company_id = current_user.company_id
    agents = (
        db.query(AIAgent)
        .filter(AIAgent.company_id == company_id)
        .order_by(AIAgent.id.asc())
        .all()
    )
    if not agents:
        return []

    configs = (
        db.query(AgentConfig)
        .filter(AgentConfig.agent_id.in_([item.id for item in agents]))
        .all()
    )
    config_by_agent = {item.agent_id: item for item in configs}
    return [
        item
        for item in agents
        if can_view_conversations(config_by_agent.get(item.id))
    ]


def _channel_label(channel_type: str | None) -> str:
    value = (channel_type or "unknown").strip().lower()
    labels = {
        "website": "Website",
        "whatsapp": "WhatsApp",
        "instagram": "Instagram",
        "voice": "Voice",
        "portal_test": "Test Console",
        "unknown": "Unclassified",
    }
    return labels.get(value, value.replace("_", " ").title())


def _session(db, company_id: int, conversation_id: int):
    return (
        db.query(WhatsAppSession)
        .filter(
            WhatsAppSession.company_id == company_id,
            WhatsAppSession.conversation_id == conversation_id,
        )
        .first()
    )


def _active_handoff(db, company_id: int, conversation_id: int):
    return (
        db.query(HumanHandoff)
        .filter(
            HumanHandoff.company_id == company_id,
            HumanHandoff.conversation_id == conversation_id,
            HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES),
        )
        .order_by(HumanHandoff.id.desc())
        .first()
    )


def _handoff_state_from_records(session=None, handoff=None):
    active = bool(handoff)
    if session is not None and human_handoff_active(session):
        active = True
    return {
        "mode": "human" if active else "ai",
        "handoff_reason": handoff.reason if handoff else (session.handoff_reason if session else None),
        "handoff_status": handoff.status if handoff else None,
    }


def _handoff_state(db, company_id: int, conversation_id: int):
    return _handoff_state_from_records(
        _session(db, company_id, conversation_id),
        _active_handoff(db, company_id, conversation_id),
    )


def _reply_capability(*, channel_type: str | None, session=None, active_whatsapp_keys=None, agent_id=None):
    normalized = (channel_type or "unknown").strip().lower()
    if normalized != "whatsapp":
        return {
            "supported": False,
            "channel": normalized,
            "reason": "Direct human replies from Xvond are currently available for WhatsApp conversations only.",
        }
    if session is None:
        return {
            "supported": False,
            "channel": "whatsapp",
            "reason": "This WhatsApp conversation is not linked to an active WhatsApp session.",
        }
    if active_whatsapp_keys is not None:
        key = (int(agent_id), str(session.phone_number_id or ""))
        if key not in active_whatsapp_keys:
            return {
                "supported": False,
                "channel": "whatsapp",
                "reason": "The WhatsApp channel used by this conversation is not active or configured.",
            }
    return {"supported": True, "channel": "whatsapp", "reason": None}


def _conversation_meta(
    item: AIConversation,
    agent: AIAgent,
    last_message,
    message_count: int,
    handoff=None,
    reply_capability=None,
):
    channel_type = item.channel_type or "unknown"
    handoff = handoff or {"mode": "ai", "handoff_reason": None, "handoff_status": None}
    return {
        "id": item.id,
        "title": item.title,
        "agent_id": agent.id,
        "agent_name": agent.name,
        "channel_id": item.channel_id,
        "channel_type": channel_type,
        "channel_label": _channel_label(channel_type),
        "external_contact_id": item.external_contact_id,
        "created_at": item.created_at,
        "message_count": message_count,
        "mode": handoff["mode"],
        "handoff_reason": handoff["handoff_reason"],
        "handoff_status": handoff["handoff_status"],
        "reply_capability": reply_capability or _reply_capability(channel_type=channel_type),
        "last_message": (
            {
                "id": last_message.id,
                "role": last_message.role,
                "content": last_message.content[:300],
                "created_at": last_message.created_at,
            }
            if last_message
            else None
        ),
    }


def _authorized_conversation(db, current_user: User, conversation_id: int):
    agents = _visible_agents(db, current_user)
    agent_map = {item.id: item for item in agents}
    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.company_id == current_user.company_id,
        )
        .first()
    )
    if conversation is None or conversation.agent_id not in agent_map:
        raise HTTPException(404, "Conversation not found")
    return conversation, agent_map[conversation.agent_id]


def _whatsapp_channel(db, conversation: AIConversation, session: WhatsAppSession):
    channels = (
        db.query(AgentChannel)
        .filter(
            AgentChannel.company_id == conversation.company_id,
            AgentChannel.agent_id == conversation.agent_id,
            AgentChannel.channel_type == "whatsapp",
            AgentChannel.enabled.is_(True),
        )
        .all()
    )
    for channel in channels:
        config = reveal_config(channel.config) or {}
        if str(config.get("phone_number_id") or "") == str(session.phone_number_id or ""):
            return channel, config
    return None, None


def _detail_reply_capability(db, conversation: AIConversation, session):
    if (conversation.channel_type or "").strip().lower() != "whatsapp":
        return _reply_capability(channel_type=conversation.channel_type)
    if session is None:
        return _reply_capability(channel_type="whatsapp", session=None)
    channel, _config = _whatsapp_channel(db, conversation, session)
    if channel is None:
        return {
            "supported": False,
            "channel": "whatsapp",
            "reason": "The WhatsApp channel used by this conversation is not active or configured.",
        }
    return {"supported": True, "channel": "whatsapp", "reason": None}


def _audit_handoff(db, *, action: str, conversation: AIConversation, current_user: User, details: dict | None = None):
    payload = {
        "agent_id": conversation.agent_id,
        "channel_type": conversation.channel_type or "unknown",
        "external_contact_id": conversation.external_contact_id,
    }
    if details:
        payload.update(details)
    audit_service.log(
        db=db,
        action=action,
        resource_type="conversation",
        resource_id=conversation.id,
        user_id=current_user.id,
        company_id=current_user.company_id,
        details=payload,
    )


@router.get("")
def list_inbox(
    agent_id: int | None = None,
    channel_type: str | None = None,
    search: str | None = None,
    limit: int = Query(default=75, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        agents = _visible_agents(db, current_user)
        agent_map = {item.id: item for item in agents}
        visible_ids = list(agent_map)
        if agent_id is not None and agent_id not in agent_map:
            raise HTTPException(403, "Conversation viewing is disabled for this AI employee")

        if not visible_ids:
            return {
                "conversations": [],
                "filters": {"agents": [], "channels": []},
                "pagination": {"total": 0, "limit": limit, "offset": offset, "has_more": False},
            }

        query = db.query(AIConversation).filter(
            AIConversation.company_id == current_user.company_id,
            AIConversation.agent_id.in_(visible_ids),
        )
        if agent_id is not None:
            query = query.filter(AIConversation.agent_id == agent_id)

        normalized_channel = str(channel_type or "").strip().lower()
        if normalized_channel:
            if normalized_channel == "unknown":
                query = query.filter(AIConversation.channel_type.is_(None))
            else:
                query = query.filter(AIConversation.channel_type == normalized_channel)

        search_value = str(search or "").strip()
        if search_value:
            pattern = f"%{search_value}%"
            query = query.filter(
                or_(
                    AIConversation.title.ilike(pattern),
                    AIConversation.external_contact_id.ilike(pattern),
                )
            )

        total = query.count()
        latest_message_id = (
            db.query(func.max(AIMessage.id))
            .filter(AIMessage.conversation_id == AIConversation.id)
            .correlate(AIConversation)
            .scalar_subquery()
        )
        conversations = (
            query.order_by(
                latest_message_id.desc().nullslast(),
                AIConversation.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        conversation_ids = [item.id for item in conversations]

        counts = {item.id: 0 for item in conversations}
        last_messages = {}
        session_by_conversation = {}
        handoff_by_conversation = {}
        if conversation_ids:
            message_stats = (
                db.query(
                    AIMessage.conversation_id,
                    func.count(AIMessage.id).label("message_count"),
                    func.max(AIMessage.id).label("last_message_id"),
                )
                .filter(AIMessage.conversation_id.in_(conversation_ids))
                .group_by(AIMessage.conversation_id)
                .all()
            )
            last_ids = []
            for row in message_stats:
                counts[row.conversation_id] = int(row.message_count or 0)
                if row.last_message_id is not None:
                    last_ids.append(row.last_message_id)
            if last_ids:
                for message in db.query(AIMessage).filter(AIMessage.id.in_(last_ids)).all():
                    last_messages[message.conversation_id] = message

            sessions = (
                db.query(WhatsAppSession)
                .filter(
                    WhatsAppSession.company_id == current_user.company_id,
                    WhatsAppSession.conversation_id.in_(conversation_ids),
                )
                .all()
            )
            session_by_conversation = {item.conversation_id: item for item in sessions}

            handoffs = (
                db.query(HumanHandoff)
                .filter(
                    HumanHandoff.company_id == current_user.company_id,
                    HumanHandoff.conversation_id.in_(conversation_ids),
                    HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES),
                )
                .order_by(HumanHandoff.id.desc())
                .all()
            )
            for handoff in handoffs:
                handoff_by_conversation.setdefault(handoff.conversation_id, handoff)

        assigned_channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id == current_user.company_id,
                AgentChannel.agent_id.in_(visible_ids),
                AgentChannel.enabled.is_(True),
            )
            .all()
        )
        active_whatsapp_keys = set()
        for channel in assigned_channels:
            if (channel.channel_type or "").strip().lower() != "whatsapp":
                continue
            config = reveal_config(channel.config) or {}
            active_whatsapp_keys.add((channel.agent_id, str(config.get("phone_number_id") or "")))

        channel_rows = (
            db.query(AIConversation.channel_type)
            .filter(
                AIConversation.company_id == current_user.company_id,
                AIConversation.agent_id.in_(visible_ids),
            )
            .distinct()
            .all()
        )
        channel_types = {
            str(item.channel_type).strip().lower()
            for item in assigned_channels
            if item.channel_type
        }
        channel_types.update(
            (row[0] or "unknown").strip().lower()
            for row in channel_rows
        )

        rows = []
        for item in conversations:
            session = session_by_conversation.get(item.id)
            handoff = handoff_by_conversation.get(item.id)
            rows.append(
                _conversation_meta(
                    item,
                    agent_map[item.agent_id],
                    last_messages.get(item.id),
                    counts.get(item.id, 0),
                    _handoff_state_from_records(session, handoff),
                    _reply_capability(
                        channel_type=item.channel_type,
                        session=session,
                        active_whatsapp_keys=active_whatsapp_keys,
                        agent_id=item.agent_id,
                    ),
                )
            )

        return {
            "conversations": rows,
            "filters": {
                "agents": [
                    {"id": item.id, "name": item.name}
                    for item in agents
                ],
                "channels": [
                    {"type": value, "label": _channel_label(value)}
                    for value in sorted(channel_types)
                ],
            },
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(conversations) < total,
            },
        }
    finally:
        db.close()


@router.get("/{conversation_id}")
def inbox_conversation(
    conversation_id: int,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        conversation, agent = _authorized_conversation(db, current_user, conversation_id)
        messages = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == conversation.id)
            .order_by(AIMessage.id.asc())
            .all()
        )
        session = _session(db, current_user.company_id, conversation.id)
        handoff = _active_handoff(db, current_user.company_id, conversation.id)
        return {
            "conversation": _conversation_meta(
                conversation,
                agent,
                messages[-1] if messages else None,
                len(messages),
                _handoff_state_from_records(session, handoff),
                _detail_reply_capability(db, conversation, session),
            ),
            "messages": [
                {
                    "id": item.id,
                    "role": item.role,
                    "content": item.content,
                    "created_at": item.created_at,
                }
                for item in messages
            ],
        }
    finally:
        db.close()


@router.post("/{conversation_id}/take-over")
def take_over_conversation(
    conversation_id: int,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        conversation, _ = _authorized_conversation(db, current_user, conversation_id)
        handoff = _active_handoff(db, current_user.company_id, conversation.id)
        if handoff is None:
            handoff = HumanHandoff(
                company_id=current_user.company_id,
                agent_id=conversation.agent_id,
                conversation_id=conversation.id,
                reason="customer_portal_takeover",
                priority="normal",
                department="customer_service",
                status="in_progress",
            )
            db.add(handoff)
        else:
            handoff.status = "in_progress"

        session = _session(db, current_user.company_id, conversation.id)
        if session is not None:
            activate_human_handoff(
                session,
                reason=handoff.reason or "customer_portal_takeover",
            )
        _audit_handoff(
            db,
            action="customer_inbox.handoff_started",
            conversation=conversation,
            current_user=current_user,
            details={"handoff_reason": handoff.reason},
        )
        db.commit()
        return {"status": "human_active", "conversation_id": conversation.id, "mode": "human"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{conversation_id}/return-ai")
def return_conversation_to_ai(
    conversation_id: int,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        conversation, _ = _authorized_conversation(db, current_user, conversation_id)
        handoffs = (
            db.query(HumanHandoff)
            .filter(
                HumanHandoff.company_id == current_user.company_id,
                HumanHandoff.conversation_id == conversation.id,
                HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES),
            )
            .all()
        )
        for handoff in handoffs:
            handoff.status = "completed"

        session = _session(db, current_user.company_id, conversation.id)
        if session is not None:
            resume_ai(session)
        _audit_handoff(
            db,
            action="customer_inbox.ai_resumed",
            conversation=conversation,
            current_user=current_user,
            details={"completed_handoffs": len(handoffs)},
        )
        db.commit()
        return {"status": "ai_active", "conversation_id": conversation.id, "mode": "ai"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{conversation_id}/message")
def send_human_reply(
    conversation_id: int,
    data: HumanReply,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        conversation, _ = _authorized_conversation(db, current_user, conversation_id)
        handoff = _active_handoff(db, current_user.company_id, conversation.id)
        if handoff is None:
            raise HTTPException(409, "Take over the conversation before replying")

        session = _session(db, current_user.company_id, conversation.id)
        if session is None:
            raise HTTPException(409, "Human replies are not available for this conversation channel yet")

        _channel, config = _whatsapp_channel(db, conversation, session)
        if config is None:
            raise HTTPException(409, "The WhatsApp channel for this conversation is not active or configured")

        text = data.message.strip()
        result = whatsapp_sender.send_text(config=config, to=session.wa_id, text=text)
        if not result.get("success"):
            raise HTTPException(502, "WhatsApp delivery failed; the reply was not recorded as sent")

        activate_human_handoff(
            session,
            reason=handoff.reason or "customer_portal_reply",
            human_message=True,
        )
        handoff.status = "in_progress"
        message = AIMessage(conversation_id=conversation.id, role="human", content=text)
        db.add(message)
        _audit_handoff(
            db,
            action="customer_inbox.human_reply_sent",
            conversation=conversation,
            current_user=current_user,
            details={
                "wa_id": session.wa_id,
                "delivery_status_code": result.get("status_code"),
            },
        )
        db.commit()
        db.refresh(message)
        return {
            "status": "sent",
            "mode": "human",
            "message": {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            },
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
