from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database.base import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, unique=True, index=True
    )

    business_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    additional_languages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(250), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    working_hours: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    locations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    services: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    service_areas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    policies: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_rules: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
