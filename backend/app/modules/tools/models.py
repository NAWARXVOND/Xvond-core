from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Index,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
