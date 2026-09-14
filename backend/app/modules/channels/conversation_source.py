from backend.app.modules.ai_agent.models import AIConversation
from backend.app.modules.channels.models import AgentChannel


def bind_conversation_source(
    db,
    *,
    conversation_id: int,
    company_id: int,
    agent_id: int,
    channel_type: str,
    channel_id: int | None = None,
    external_contact_id: str | None = None,
) -> AIConversation:
    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.company_id == company_id,
            AIConversation.agent_id == agent_id,
        )
        .first()
    )
    if conversation is None:
        raise ValueError("Conversation not found for source binding")

    normalized_type = str(channel_type or "").strip().lower()
    if not normalized_type:
        raise ValueError("Conversation channel type is required")

    if channel_id is not None:
        channel = db.query(AgentChannel).filter(
            AgentChannel.id == channel_id,
            AgentChannel.company_id == company_id,
            AgentChannel.agent_id == agent_id,
            AgentChannel.channel_type == normalized_type,
        ).first()
        if channel is None:
            raise ValueError("Channel does not belong to this company and employee")
    contact = str(external_contact_id or "").strip()
    if len(contact) > 200:
        raise ValueError("External contact identity is too long")
    if conversation.external_contact_id and contact and conversation.external_contact_id != contact:
        raise ValueError("Conversation is already bound to another contact")

    if conversation.channel_type and conversation.channel_type != normalized_type:
        raise ValueError("Conversation is already bound to another channel type")
    if conversation.channel_id and channel_id and conversation.channel_id != channel_id:
        raise ValueError("Conversation is already bound to another channel")

    conversation.channel_type = conversation.channel_type or normalized_type
    if channel_id is not None:
        conversation.channel_id = conversation.channel_id or channel_id
    if external_contact_id:
        conversation.external_contact_id = (
            conversation.external_contact_id or contact
        )
    db.flush()
    return conversation
