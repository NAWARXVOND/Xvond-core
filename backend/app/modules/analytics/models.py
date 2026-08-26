from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from backend.app.core.database.base import Base


class AnalyticsSource(Base):
    __tablename__ = "analytics_sources"
    __table_args__ = (
        Index("ix_analytics_sources_company_enabled", "company_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    integration_id: Mapped[int | None] = mapped_column(ForeignKey("company_integrations.id"), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    @validates("config")
    def protect_stored_config(self, _key, value):
        from backend.app.core.config_secrets import protect_config
        return protect_config(value or {})


class AnalyticsDashboard(Base):
    __tablename__ = "analytics_dashboards"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    metrics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AnalyticsRecord(Base):
    __tablename__ = "analytics_records"
    __table_args__ = (
        Index("ix_analytics_records_company_source_created", "company_id", "source_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("analytics_sources.id"), nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
