from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base


class CompanySolution(Base):
    __tablename__ = "company_solutions"
    __table_args__ = (
        Index("ix_company_solutions_company_status", "company_id", "status"),
        Index("ix_company_solutions_service", "service_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    service_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    package_tier: Mapped[str] = mapped_column(
        String(50), default="business", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="setup", nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    linked_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_agents.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
