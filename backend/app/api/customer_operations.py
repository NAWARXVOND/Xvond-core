from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.customer_ops import service as customer_ops


router = APIRouter(
    prefix="/customer/operations",
    tags=["Customer Operations Workspace"],
)


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class NotificationPreferenceUpdate(BaseModel):
    enabled: bool = True
    event_types: list[str] = Field(
        default_factory=lambda: list(customer_ops.DEFAULT_EVENTS)
    )
    destinations: list[str] = Field(default_factory=lambda: ["dashboard"])


def company_id_for(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(status_code=403, detail="Customer company required")
    return int(user.company_id)


@router.get("/customers")
def customers(current_user: User = Depends(require_customer_manager)):
    db = SessionLocal()
    try:
        company_id = company_id_for(current_user)
        return {"customers": customer_ops.list_customers(db, company_id)}
    finally:
        db.close()


@router.get("/customers/{customer_id}")
def customer_detail(
    customer_id: int,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        result = customer_ops.customer_detail(
            db,
            company_id_for(current_user),
            customer_id,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return result
    finally:
        db.close()


@router.put("/customers/{customer_id}")
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        try:
            row = customer_ops.update_customer(
                db,
                company_id_for(current_user),
                customer_id,
                name=data.name,
                phone=data.phone,
                email=data.email,
                tags=data.tags,
                notes=data.notes,
            )
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {"status": "updated", "customer_id": row.id}
    finally:
        db.close()


@router.get("/notifications")
def notifications(current_user: User = Depends(require_customer_manager)):
    db = SessionLocal()
    try:
        return customer_ops.notification_feed(db, company_id_for(current_user))
    finally:
        db.close()


@router.put("/notification-preferences")
def update_notification_preferences(
    data: NotificationPreferenceUpdate,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        row = customer_ops.update_notification_preferences(
            db,
            company_id_for(current_user),
            enabled=data.enabled,
            event_types=data.event_types,
            destinations=data.destinations,
        )
        return {
            "status": "updated",
            "preferences": {
                "enabled": row.enabled,
                "event_types": row.event_types or [],
                "destinations": row.destinations or ["dashboard"],
            },
        }
    finally:
        db.close()


@router.post("/notifications/read-all")
def read_all_notifications(
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        updated = customer_ops.mark_all_notifications_read(
            db,
            company_id_for(current_user),
        )
        return {"status": "updated", "updated": updated}
    finally:
        db.close()


@router.get("/analytics")
def business_analytics(
    days: int = 30,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        return customer_ops.business_analytics(
            db,
            company_id_for(current_user),
            days=days,
        )
    finally:
        db.close()
