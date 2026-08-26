from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.app.core.database.base import Base


def _utc_now_naive() -> datetime:
    """Return current UTC time without tzinfo for existing naive DB columns.

    Python 3.14 deprecates datetime.utcnow(). Keeping the stored representation
    naive avoids a schema migration while still sourcing the value from an
    explicit UTC-aware clock.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class AIProviderRecord(Base):
    __tablename__ = "ai_provider_records"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        default=100,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now_naive,
        nullable=False,
    )


class AIModelRecord(Base):
    __tablename__ = "ai_model_records"

    __table_args__ = (
        UniqueConstraint(
            "provider_name",
            "model_name",
            name="uq_provider_model",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    provider_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    model_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    input_price_per_million: Mapped[Decimal] = mapped_column(
        Numeric(14, 6),
        default=Decimal("0"),
        nullable=False,
    )

    output_price_per_million: Mapped[Decimal] = mapped_column(
        Numeric(14, 6),
        default=Decimal("0"),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now_naive,
        nullable=False,
    )


class CompanyAIProfile(Base):
    __tablename__ = "company_ai_profiles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    default_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    default_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    allow_fallback: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    fallback_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    fallback_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
