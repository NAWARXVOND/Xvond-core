from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.ai_agent.customer_access import can_view_conversations
from backend.app.modules.ai_agent.factory_models import AgentConfig
from backend.app.modules.ai_agent.models import AIAgent, AIConversation, AIMessage
from backend.app.modules.channels.models import AgentChannel

router = APIRouter(prefix="/customer/inbox", tags=["Customer Conversation Inbox"])


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


def _conversation_meta(item: AIConversation, agent: AIAgent, last_message, message_count: int):
    channel_type = item.channel_type or "unknown"
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


@router.get("")
def list_inbox(
    agent_id: int | None = None,
    channel_type: str | None = None,
    search: str | None = None,
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
            return {"conversations": [], "filters": {"agents": [], "channels": []}}

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

        conversations = query.order_by(AIConversation.id.desc()).limit(500).all()
        conversation_ids = [item.id for item in conversations]
        last_messages = {}
        counts = {item.id: 0 for item in conversations}
        if conversation_ids:
            messages = (
                db.query(AIMessage)
                .filter(AIMessage.conversation_id.in_(conversation_ids))
                .order_by(AIMessage.id.desc())
                .all()
            )
            for message in messages:
                counts[message.conversation_id] = counts.get(message.conversation_id, 0) + 1
                last_messages.setdefault(message.conversation_id, message)

        assigned_channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id == current_user.company_id,
                AgentChannel.agent_id.in_(visible_ids),
                AgentChannel.enabled.is_(True),
            )
            .all()
        )
        channel_types = {
            str(item.channel_type).strip().lower()
            for item in assigned_channels
            if item.channel_type
        }
        channel_types.update(
            (item.channel_type or "unknown").strip().lower()
            for item in conversations
        )

        return {
            "conversations": [
                _conversation_meta(
                    item,
                    agent_map[item.agent_id],
                    last_messages.get(item.id),
                    counts.get(item.id, 0),
                )
                for item in conversations
            ],
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

        messages = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == conversation.id)
            .order_by(AIMessage.id.asc())
            .all()
        )
        return {
            "conversation": _conversation_meta(
                conversation,
                agent_map[conversation.agent_id],
                messages[-1] if messages else None,
                len(messages),
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
