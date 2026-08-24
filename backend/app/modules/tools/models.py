from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    validates,
)

from backend.app.core.database.base import Base


class AgentToolAssignment(Base):
    __tablename__ = "agent_tool_assignments"

    __table_args__ = (
        Index(
            "uq_agent_tool_assignment",
            "agent_id",
            "tool_name",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("ai_agents.id"),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    config: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


    @validates("config")
    def protect_stored_config(self, _key, value):
        from backend.app.core.config_secrets import protect_config
        return protect_config(value or {})

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class ToolApprovalRequest(Base):
    __tablename__ = "tool_approval_requests"

    __table_args__ = (
        Index(
            "ix_tool_approval_company_status",
            "company_id",
            "status",
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
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_conversations.id"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    arguments: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )
    result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    decision_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
