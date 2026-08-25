from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.billing.cycle import _add_month
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.billing.service_models import ServicePlan, ServiceSubscription
from backend.app.modules.solutions.catalog import PACKAGE_TIERS, SERVICE_CATALOG

router = APIRouter(prefix="/admin/service-billing", tags=["Xvond Admin - Service Billing"])


class ServicePlanInput(BaseModel):
    service_code: str
    tier: str
    name: str
    monthly_price: Decimal = Field(ge=0)
    currency: str = "OMR"
    limits: dict = Field(default_factory=dict)


class ServiceSubscriptionInput(BaseModel):
    plan_id: int


def plan_data(item):
    return {
        "id": item.id,
        "service_code": item.service_code,
        "tier": item.tier,
        "name": item.name,
        "monthly_price": item.monthly_price,
        "currency": item.currency,
        "limits": item.limits,
        "enabled": item.enabled,
    }


@router.get("/plans")
def list_plans(current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        items = db.query(ServicePlan).order_by(ServicePlan.service_code, ServicePlan.monthly_price).all()
        return {"plans": [plan_data(item) for item in items]}
    finally:
        db.close()


@router.post("/plans")
def create_plan(data: ServicePlanInput, current_admin: User = Depends(require_xvond_admin)):
    service_code = data.service_code.strip().lower()
    tier = data.tier.strip().lower()
    if service_code not in SERVICE_CATALOG:
        raise HTTPException(status_code=400, detail="Unsupported service")
    if tier not in PACKAGE_TIERS:
        raise HTTPException(status_code=400, detail="Unsupported package tier")
    db = SessionLocal()
    try:
        duplicate = db.query(ServicePlan).filter(
            ServicePlan.service_code == service_code,
            ServicePlan.tier == tier,
        ).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Service plan already exists")
        item = ServicePlan(
            service_code=service_code,
            tier=tier,
            name=data.name.strip() or PACKAGE_TIERS[tier],
            monthly_price=data.monthly_price,
            currency=(data.currency or "OMR").strip().upper(),
            limits=data.limits or {},
            enabled=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return plan_data(item)
    finally:
        db.close()


@router.put("/companies/{company_id}/services/{service_code}")
def subscribe_service(
    company_id: int,
    service_code: str,
    data: ServiceSubscriptionInput,
    current_admin: User = Depends(require_xvond_admin),
):
    service_code = service_code.strip().lower()
    if service_code not in SERVICE_CATALOG:
        raise HTTPException(status_code=400, detail="Unsupported service")
    db = SessionLocal()
    try:
        if db.get(Company, company_id) is None:
            raise HTTPException(status_code=404, detail="Company not found")
        plan = db.query(ServicePlan).filter(
            ServicePlan.id == data.plan_id,
            ServicePlan.service_code == service_code,
            ServicePlan.enabled.is_(True),
        ).first()
        if plan is None:
            raise HTTPException(status_code=404, detail="Service plan not found")
        now = datetime.utcnow()
        item = db.query(ServiceSubscription).filter(
            ServiceSubscription.company_id == company_id,
            ServiceSubscription.service_code == service_code,
        ).first()
        if item is None:
            item = ServiceSubscription(
                company_id=company_id,
                service_code=service_code,
                plan_id=plan.id,
                status="active",
                current_period_start=now,
                current_period_end=_add_month(now),
            )
            db.add(item)
        else:
            item.plan_id = plan.id
            item.status = "active"
            item.current_period_start = now
            item.current_period_end = _add_month(now)
        db.commit()
        db.refresh(item)
        return company_service_data(db, item, plan)
    finally:
        db.close()


def company_service_data(db, item, plan=None):
    plan = plan or db.get(ServicePlan, item.plan_id)
    usage = {}
    for metric, limit in (plan.limits or {}).items():
        usage[metric] = {
            "used": service_limits.used(db, item, metric),
            "limit": limit,
        }
    return {
        "id": item.id,
        "company_id": item.company_id,
        "service_code": item.service_code,
        "service_name": SERVICE_CATALOG.get(item.service_code, {}).get("name", item.service_code),
        "status": item.status,
        "plan": plan_data(plan),
        "current_period_start": item.current_period_start,
        "current_period_end": item.current_period_end,
        "usage": usage,
    }


@router.get("/companies/{company_id}")
def company_services(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        if db.get(Company, company_id) is None:
            raise HTTPException(status_code=404, detail="Company not found")
        items = db.query(ServiceSubscription).filter(
            ServiceSubscription.company_id == company_id
        ).order_by(ServiceSubscription.service_code).all()
        return {"company_id": company_id, "services": [company_service_data(db, item) for item in items]}
    finally:
        db.close()


@router.patch("/companies/{company_id}/services/{service_code}/pause")
def pause_service(company_id: int, service_code: str, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        item = db.query(ServiceSubscription).filter(
            ServiceSubscription.company_id == company_id,
            ServiceSubscription.service_code == service_code.strip().lower(),
        ).first()
        if item is None:
            raise HTTPException(status_code=404, detail="Service subscription not found")
        item.status = "paused"
        db.commit()
        return {"status": "paused", "service_code": item.service_code}
    finally:
        db.close()
