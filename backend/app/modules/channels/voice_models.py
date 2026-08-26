from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base


class VoiceCallSession(Base):
    __tablename__ = "voice_call_sessions"

    __table_args__ = (
        Index(
            "uq_voice_call_sessions_channel_external",
            "channel_id",
            "external_call_id",
            unique=True,
        ),
        Index(
            "ix_voice_call_sessions_company_agent",
            "company_id",
            "agent_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
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
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("agent_channels.id"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_conversations.id"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        default="vapi",
        nullable=False,
    )
    external_call_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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
