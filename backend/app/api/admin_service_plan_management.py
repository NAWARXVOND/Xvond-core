from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.billing.service_models import ServicePlan

router = APIRouter(prefix="/admin/service-billing", tags=["Xvond Admin - Service Billing"])


class ServicePlanUpdate(BaseModel):
    name: str | None = None
    monthly_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    limits: dict | None = None
    enabled: bool | None = None


@router.patch("/plans/{plan_id}")
def update_service_plan(
    plan_id: int,
    data: ServicePlanUpdate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        item = db.get(ServicePlan, plan_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Service plan not found")

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="Plan name cannot be empty")
            item.name = name
        if data.monthly_price is not None:
            item.monthly_price = data.monthly_price
        if data.currency is not None:
            currency = data.currency.strip().upper()
            if not currency:
                raise HTTPException(status_code=400, detail="Currency cannot be empty")
            item.currency = currency
        if data.limits is not None:
            item.limits = data.limits
        if data.enabled is not None:
            item.enabled = data.enabled

        db.commit()
        db.refresh(item)
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
    finally:
        db.close()
