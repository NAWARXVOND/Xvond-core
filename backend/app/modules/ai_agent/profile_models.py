from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base


class AIAgentProfile(Base):
    __tablename__ = "ai_agent_profiles"
    __table_args__ = (UniqueConstraint("agent_id", name="uq_ai_agent_profiles_agent_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reply_language: Mapped[str] = mapped_column(String(50), default="auto", nullable=False)
    conversation_style: Mapped[str] = mapped_column(String(80), default="professional_friendly", nullable=False)
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
