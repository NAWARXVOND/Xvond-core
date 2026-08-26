from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func

from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import configured_secret_fields, public_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.analytics.models import (
    AnalyticsDashboard,
    AnalyticsRecord,
    AnalyticsSource,
)
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.integrations.models import CompanyIntegration

router = APIRouter(prefix="/admin/analytics-builder", tags=["Xvond Admin - Analytics"])

ALLOWED_SOURCE_TYPES = {"integration", "database", "csv", "api", "manual"}


class SourceCreate(BaseModel):
    name: str
    source_type: str
    integration_id: int | None = None
    config: dict = Field(default_factory=dict)


class DashboardCreate(BaseModel):
    name: str
    metrics: list[dict] = Field(default_factory=list)
    configuration: dict = Field(default_factory=dict)


class RecordCreate(BaseModel):
    data: dict
    occurred_at: datetime | None = None


class RecordBatchCreate(BaseModel):
    records: list[RecordCreate] = Field(min_length=1, max_length=1000)


def require_company(db, company_id: int):
    item = db.query(Company).filter(Company.id == company_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return item


def require_source(db, company_id: int, source_id: int):
    item = db.query(AnalyticsSource).filter(
        AnalyticsSource.id == source_id,
        AnalyticsSource.company_id == company_id,
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Analytics source not found")
    return item


def numeric(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def summarize_records(records):
    numeric_values = {}
    categorical_values = {}

    for record in records:
        for key, value in (record.data or {}).items():
            number = numeric(value)
            if number is not None:
                numeric_values.setdefault(key, []).append(number)
            elif isinstance(value, (str, bool)):
                bucket = categorical_values.setdefault(key, {})
                label = str(value)
                bucket[label] = bucket.get(label, 0) + 1

    metrics = {}
    for key, values in numeric_values.items():
        total = sum(values, Decimal("0"))
        metrics[key] = {
            "count": len(values),
            "sum": str(total),
            "average": str(total / len(values)) if values else "0",
            "min": str(min(values)),
            "max": str(max(values)),
        }

    categories = {}
    for key, values in categorical_values.items():
        categories[key] = sorted(
            ({"value": value, "count": count} for value, count in values.items()),
            key=lambda item: item["count"],
            reverse=True,
        )[:20]

    return {
        "record_count": len(records),
        "numeric_metrics": metrics,
        "categories": categories,
    }


@router.get("/companies/{company_id}")
def workspace(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        sources = db.query(AnalyticsSource).filter(
            AnalyticsSource.company_id == company_id
        ).order_by(AnalyticsSource.id.desc()).all()
        dashboards = db.query(AnalyticsDashboard).filter(
            AnalyticsDashboard.company_id == company_id
        ).order_by(AnalyticsDashboard.id.desc()).all()
        return {
            "company_id": company_id,
            "sources": [{
                "id": x.id,
                "name": x.name,
                "source_type": x.source_type,
                "integration_id": x.integration_id,
                "config": public_config(x.config),
                "configured_secret_fields": configured_secret_fields(x.config),
                "enabled": x.enabled,
                "record_count": db.query(func.count(AnalyticsRecord.id)).filter(
                    AnalyticsRecord.source_id == x.id
                ).scalar() or 0,
                "created_at": x.created_at,
            } for x in sources],
            "dashboards": [{
                "id": x.id,
                "name": x.name,
                "metrics": x.metrics,
                "configuration": x.configuration,
                "enabled": x.enabled,
                "created_at": x.created_at,
            } for x in dashboards],
        }
    finally:
        db.close()


@router.post("/companies/{company_id}/sources")
def create_source(company_id: int, data: SourceCreate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        if settings.is_production:
            current = db.query(func.count(AnalyticsSource.id)).filter(
                AnalyticsSource.company_id == company_id,
                AnalyticsSource.enabled.is_(True),
            ).scalar() or 0
            service_limits.check_current(
                db, company_id, "analytics", "data_sources", current
            )
        source_type = data.source_type.strip().lower()
        if source_type not in ALLOWED_SOURCE_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported analytics source type")
        if data.integration_id is not None:
            integration = db.query(CompanyIntegration).filter(
                CompanyIntegration.id == data.integration_id,
                CompanyIntegration.company_id == company_id,
            ).first()
            if integration is None:
                raise HTTPException(status_code=400, detail="Integration does not belong to company")
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Source name is required")
        item = AnalyticsSource(
            company_id=company_id,
            name=name,
            source_type=source_type,
            integration_id=data.integration_id,
            config=data.config or {},
            enabled=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {
            "id": item.id,
            "status": "created",
            "config": public_config(item.config),
            "configured_secret_fields": configured_secret_fields(item.config),
        }
    finally:
        db.close()


@router.post("/companies/{company_id}/sources/{source_id}/records")
def ingest_records(
    company_id: int,
    source_id: int,
    data: RecordBatchCreate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        source = require_source(db, company_id, source_id)
        if not source.enabled:
            raise HTTPException(status_code=400, detail="Analytics source is disabled")
        if settings.is_production:
            service_limits.check(
                db, company_id, "analytics", "records_ingested", len(data.records)
            )
        for record in data.records:
            db.add(
                AnalyticsRecord(
                    company_id=company_id,
                    source_id=source_id,
                    data=record.data,
                    occurred_at=record.occurred_at,
                )
            )
        if settings.is_production:
            service_limits.record(
                db,
                company_id,
                "analytics",
                "records_ingested",
                len(data.records),
                metadata={"source_id": source_id},
            )
        db.commit()
        return {"status": "ingested", "records": len(data.records)}
    finally:
        db.close()


@router.get("/companies/{company_id}/sources/{source_id}/summary")
def source_summary(
    company_id: int,
    source_id: int,
    limit: int = 5000,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        require_source(db, company_id, source_id)
        limit = max(1, min(limit, 5000))
        records = db.query(AnalyticsRecord).filter(
            AnalyticsRecord.company_id == company_id,
            AnalyticsRecord.source_id == source_id,
        ).order_by(AnalyticsRecord.id.desc()).limit(limit).all()
        return summarize_records(records)
    finally:
        db.close()


@router.post("/companies/{company_id}/dashboards")
def create_dashboard(company_id: int, data: DashboardCreate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
        if settings.is_production:
            current = db.query(func.count(AnalyticsDashboard.id)).filter(
                AnalyticsDashboard.company_id == company_id,
                AnalyticsDashboard.enabled.is_(True),
            ).scalar() or 0
            service_limits.check_current(
                db, company_id, "analytics", "dashboards", current
            )
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Dashboard name is required")
        item = AnalyticsDashboard(
            company_id=company_id,
            name=name,
            metrics=data.metrics or [],
            configuration=data.configuration or {},
            enabled=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"id": item.id, "status": "created"}
    finally:
        db.close()
