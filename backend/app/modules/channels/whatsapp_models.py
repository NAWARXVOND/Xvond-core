from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base


class WhatsAppSession(Base):
    __tablename__ = "whatsapp_sessions"

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "wa_id",
            name="uq_whatsapp_agent_contact",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("ai_agents.id"),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id"),
        nullable=False,
        index=True,
    )

    wa_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    phone_number_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    automation_state: Mapped[str] = mapped_column(
        String(20),
        default="ai",
        nullable=False,
    )

    handoff_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    human_takeover_until: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_human_message_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class WhatsAppInboundMessage(Base):
    __tablename__ = "whatsapp_inbound_messages"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    external_message_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("ai_agents.id"),
        nullable=False,
        index=True,
    )

    wa_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
