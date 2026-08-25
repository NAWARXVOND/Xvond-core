from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.analytics.models import AnalyticsSource, AnalyticsDashboard
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


def require_company(db, company_id: int):
    item = db.query(Company).filter(Company.id == company_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return item


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
                "config": x.config,
                "enabled": x.enabled,
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
        item = AnalyticsSource(
            company_id=company_id,
            name=data.name.strip(),
            source_type=source_type,
            integration_id=data.integration_id,
            config=data.config or {},
            enabled=True,
        )
        if not item.name:
            raise HTTPException(status_code=400, detail="Source name is required")
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"id": item.id, "status": "created"}
    finally:
        db.close()


@router.post("/companies/{company_id}/dashboards")
def create_dashboard(company_id: int, data: DashboardCreate, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        require_company(db, company_id)
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
