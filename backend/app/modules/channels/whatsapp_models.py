from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    update,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base
from backend.app.modules.ai_agent.models import AIConversation


class WhatsAppSession(Base):
    __tablename__ = "whatsapp_sessions"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "phone_number_id",
            "wa_id",
            name="uq_whatsapp_channel_contact",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"), nullable=False, index=True)
    wa_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    phone_number_id: Mapped[str] = mapped_column(String(150), nullable=False)
    automation_state: Mapped[str] = mapped_column(String(20), default="ai", nullable=False)
    handoff_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_takeover_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_human_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_resumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_resume_echo_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


@event.listens_for(WhatsAppSession, "after_insert")
def _bind_whatsapp_conversation_source(_mapper, connection, target):
    connection.execute(
        update(AIConversation)
        .where(
            AIConversation.id == target.conversation_id,
            AIConversation.company_id == target.company_id,
            AIConversation.agent_id == target.agent_id,
            AIConversation.channel_type.is_(None),
        )
        .values(channel_type="whatsapp", external_contact_id=target.wa_id)
    )


class WhatsAppInboundMessage(Base):
    __tablename__ = "whatsapp_inbound_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False, index=True)
    wa_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # processing can survive an inner business-action commit. A later queue retry
    # may resume it; processed/ignored are terminal and are treated as duplicates.
    status: Mapped[str] = mapped_column(String(30), default="processing", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class WhatsAppOutboundDelivery(Base):
    """Durable transport state for one WhatsApp outbound message.

    Conversation content remains in AIMessage. This row stores only routing and
    provider lifecycle metadata so delivery can be retried/reconciled without
    repeating the AI turn or any business side effect.
    """

    __tablename__ = "whatsapp_outbound_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_whatsapp_outbound_idempotency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("agent_channels.id"), nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("ai_messages.id"), nullable=False, index=True)
    inbound_external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    wa_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
