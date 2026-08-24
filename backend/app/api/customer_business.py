from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import (
    require_customer_manager,
)
from backend.app.models.user import User

from backend.app.modules.tools.business_models import (
    Lead,
    Booking,
    Order,
    HumanHandoff,
)


router = APIRouter(
    prefix="/customer/business",
    tags=["Customer Business Operations"],
)


def company_id_for(user: User) -> int:

    if user.company_id is None:
        raise HTTPException(
            status_code=403,
            detail="Customer company required",
        )

    return user.company_id


@router.get("/leads")
def leads(
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()

    try:
        company_id = company_id_for(current_user)

        return (
            db.query(Lead)
            .filter(Lead.company_id == company_id)
            .order_by(Lead.id.desc())
            .all()
        )

    finally:
        db.close()


@router.get("/bookings")
def bookings(
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()

    try:
        company_id = company_id_for(current_user)

        return (
            db.query(Booking)
            .filter(Booking.company_id == company_id)
            .order_by(Booking.id.desc())
            .all()
        )

    finally:
        db.close()


@router.get("/orders")
def orders(
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()

    try:
        company_id = company_id_for(current_user)

        return (
            db.query(Order)
            .filter(Order.company_id == company_id)
            .order_by(Order.id.desc())
            .all()
        )

    finally:
        db.close()


@router.get("/handoffs")
def handoffs(
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()

    try:
        company_id = company_id_for(current_user)

        return (
            db.query(HumanHandoff)
            .filter(HumanHandoff.company_id == company_id)
            .order_by(HumanHandoff.id.desc())
            .all()
        )

    finally:
        db.close()

