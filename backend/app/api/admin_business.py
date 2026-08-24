from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.tools.business_models import (
    Lead,
    Booking,
    Order,
    HumanHandoff,
)

from backend.app.modules.audit.service import (
    audit_service,
)


router = APIRouter(
    prefix="/admin/business",
    tags=["Xvond Admin - Business Operations"],
)


BUSINESS_STATUSES = {
    "lead": {
        "new",
        "contacted",
        "qualified",
        "won",
        "lost",
        "closed",
    },

    "booking": {
        "pending",
        "confirmed",
        "completed",
        "cancelled",
        "no_show",
    },

    "order": {
        "new",
        "confirmed",
        "processing",
        "completed",
        "cancelled",
    },

    "handoff": {
        "pending",
        "assigned",
        "resolved",
        "closed",
        "cancelled",
    },
}


def normalize_status(
    resource_type: str,
    status: str,
):

    value = (
        status
        .strip()
        .lower()
    )

    allowed = BUSINESS_STATUSES[
        resource_type
    ]

    if value not in allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "message":
                    "Invalid status",
                "resource_type":
                    resource_type,
                "allowed":
                    sorted(allowed),
            },
        )

    return value


def lead_data(item):
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "name": item.name,
        "phone": item.phone,
        "email": item.email,
        "interest": item.interest,
        "notes": item.notes,
        "status": item.status,
        "created_at": item.created_at,
    }


def booking_data(item):
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "customer_name": item.customer_name,
        "phone": item.phone,
        "service": item.service,
        "date": item.booking_date,
        "time": item.booking_time,
        "status": item.status,
        "created_at": item.created_at,
    }


def order_data(item):
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "customer_name": item.customer_name,
        "phone": item.phone,
        "items": item.items,
        "delivery_address": item.delivery_address,
        "notes": item.notes,
        "status": item.status,
        "created_at": item.created_at,
    }


def handoff_data(item):
    return {
        "id": item.id,
        "company_id": item.company_id,
        "agent_id": item.agent_id,
        "conversation_id": item.conversation_id,
        "reason": item.reason,
        "priority": item.priority,
        "department": item.department,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.get("/leads")
def list_leads(
    company_id: int | None = None,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        query = db.query(Lead)

        if company_id is not None:
            query = query.filter(
                Lead.company_id == company_id
            )

        items = query.order_by(
            Lead.id.desc()
        ).all()

        return [lead_data(x) for x in items]

    finally:
        db.close()


@router.get("/bookings")
def list_bookings(
    company_id: int | None = None,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        query = db.query(Booking)

        if company_id is not None:
            query = query.filter(
                Booking.company_id == company_id
            )

        items = query.order_by(
            Booking.id.desc()
        ).all()

        return [booking_data(x) for x in items]

    finally:
        db.close()


@router.get("/orders")
def list_orders(
    company_id: int | None = None,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        query = db.query(Order)

        if company_id is not None:
            query = query.filter(
                Order.company_id == company_id
            )

        items = query.order_by(
            Order.id.desc()
        ).all()

        return [order_data(x) for x in items]

    finally:
        db.close()


@router.get("/handoffs")
def list_handoffs(
    company_id: int | None = None,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        query = db.query(HumanHandoff)

        if company_id is not None:
            query = query.filter(
                HumanHandoff.company_id == company_id
            )

        items = query.order_by(
            HumanHandoff.id.desc()
        ).all()

        return [handoff_data(x) for x in items]

    finally:
        db.close()


@router.patch("/leads/{lead_id}/status/{status}")
def update_lead_status(
    lead_id: int,
    status: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        item = db.get(Lead, lead_id)

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Lead not found",
            )

        item.status = normalize_status(
            "lead",
            status,
        )

        audit_service.log(
            db=db,
            user_id=current_admin.id,
            company_id=item.company_id,
            action="lead.status_changed",
            resource_type="lead",
            resource_id=item.id,
            details={
                "new_status":
                    item.status,
            },
        )
        db.commit()
        db.refresh(item)

        return lead_data(item)

    finally:
        db.close()


@router.patch("/bookings/{booking_id}/status/{status}")
def update_booking_status(
    booking_id: int,
    status: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        item = db.get(Booking, booking_id)

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Booking not found",
            )

        item.status = normalize_status(
            "booking",
            status,
        )

        audit_service.log(
            db=db,
            user_id=current_admin.id,
            company_id=item.company_id,
            action="booking.status_changed",
            resource_type="booking",
            resource_id=item.id,
            details={
                "new_status":
                    item.status,
            },
        )
        db.commit()
        db.refresh(item)

        return booking_data(item)

    finally:
        db.close()


@router.patch("/orders/{order_id}/status/{status}")
def update_order_status(
    order_id: int,
    status: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        item = db.get(Order, order_id)

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        item.status = normalize_status(
            "order",
            status,
        )

        audit_service.log(
            db=db,
            user_id=current_admin.id,
            company_id=item.company_id,
            action="order.status_changed",
            resource_type="order",
            resource_id=item.id,
            details={
                "new_status":
                    item.status,
            },
        )
        db.commit()
        db.refresh(item)

        return order_data(item)

    finally:
        db.close()


@router.patch("/handoffs/{handoff_id}/status/{status}")
def update_handoff_status(
    handoff_id: int,
    status: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        item = db.get(
            HumanHandoff,
            handoff_id,
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Handoff not found",
            )

        item.status = normalize_status(
            "handoff",
            status,
        )

        audit_service.log(
            db=db,
            user_id=current_admin.id,
            company_id=item.company_id,
            action="handoff.status_changed",
            resource_type="handoff",
            resource_id=item.id,
            details={
                "new_status":
                    item.status,
            },
        )
        db.commit()
        db.refresh(item)

        return handoff_data(item)

    finally:
        db.close()
