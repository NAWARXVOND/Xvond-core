from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base


class AutomationWorkflow(Base):
    __tablename__ = "automation_workflows"
    __table_args__ = (
        Index("ix_automation_workflows_company_enabled", "company_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        Index("ix_automation_runs_company_created", "company_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("automation_workflows.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
