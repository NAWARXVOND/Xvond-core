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
    validates,
)

from backend.app.core.database.base import Base


class AgentChannel(Base):
    __tablename__ = "agent_channels"

    __table_args__ = (
        Index(
            "uq_agent_channels_agent_type",
            "agent_id",
            "channel_type",
            unique=True,
        ),
        Index(
            "ix_agent_channels_company_enabled",
            "company_id",
            "enabled",
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

    channel_type: Mapped[str] = mapped_column(
        String(100),
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
