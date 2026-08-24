
from datetime import datetime
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.billing.models import (
    Plan,
    Subscription,
)


router = APIRouter(
    prefix="/admin/billing",
    tags=["Xvond Admin - Billing"],
)


class PlanCreate(BaseModel):
    name: str
    price: Decimal = Field(ge=0)
    agent_limit: int = Field(ge=0)
    token_limit: int = Field(ge=0)
    channel_limit: int = Field(ge=0)


class PlanUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = Field(
        default=None,
        ge=0,
    )
    agent_limit: int | None = Field(
        default=None,
        ge=0,
    )
    token_limit: int | None = Field(
        default=None,
        ge=0,
    )
    channel_limit: int | None = Field(
        default=None,
        ge=0,
    )
    enabled: bool | None = None


class SubscriptionCreate(BaseModel):
    plan_id: int


class SubscriptionUpdate(BaseModel):
    plan_id: int | None = None
    status: str | None = None


def serialize_plan(plan: Plan):

    return {
        "id": plan.id,
        "name": plan.name,
        "price": plan.price,
        "agent_limit": plan.agent_limit,
        "token_limit": plan.token_limit,
        "channel_limit": plan.channel_limit,
        "enabled": plan.enabled,
    }


def serialize_subscription(
    subscription: Subscription,
    plan: Plan | None = None,
):

    return {
        "id": subscription.id,
        "company_id": subscription.company_id,
        "plan_id": subscription.plan_id,
        "plan_name": (
            plan.name
            if plan
            else None
        ),
        "status": subscription.status,
        "started_at": subscription.started_at,
    }


def get_company_or_404(
    db,
    company_id: int,
):

    company = (
        db.query(Company)
        .filter(
            Company.id == company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return company


def get_plan_or_404(
    db,
    plan_id: int,
    require_enabled: bool = False,
):

    query = (
        db.query(Plan)
        .filter(
            Plan.id == plan_id
        )
    )

    if require_enabled:
        query = query.filter(
            Plan.enabled.is_(True)
        )

    plan = query.first()

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Plan not found",
        )

    return plan


@router.post("/plans")
def create_plan(
    data: PlanCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Plan name is required",
            )

        existing = (
            db.query(Plan)
            .filter(
                Plan.name == name
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=400,
                detail="Plan already exists",
            )

        plan = Plan(
            name=name,
            price=data.price,
            agent_limit=data.agent_limit,
            token_limit=data.token_limit,
            channel_limit=data.channel_limit,
            enabled=True,
        )

        db.add(plan)
        db.commit()
        db.refresh(plan)

        result = serialize_plan(plan)
        result["status"] = "created"

        return result

    finally:
        db.close()


@router.get("/plans")
def list_plans(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        plans = (
            db.query(Plan)
            .order_by(
                Plan.id.asc()
            )
            .all()
        )

        return {
            "plans": [
                serialize_plan(item)
                for item in plans
            ]
        }

    finally:
        db.close()


@router.patch(
    "/plans/{plan_id}"
)
def update_plan(
    plan_id: int,
    data: PlanUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        plan = get_plan_or_404(
            db,
            plan_id,
        )

        if data.name is not None:

            name = data.name.strip()

            if not name:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Plan name cannot be empty"
                    ),
                )

            duplicate = (
                db.query(Plan)
                .filter(
                    Plan.name == name,
                    Plan.id != plan.id,
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=400,
                    detail="Plan name already exists",
                )

            plan.name = name

        for field in (
            "price",
            "agent_limit",
            "token_limit",
            "channel_limit",
            "enabled",
        ):

            value = getattr(
                data,
                field,
            )

            if value is not None:
                setattr(
                    plan,
                    field,
                    value,
                )

        db.commit()
        db.refresh(plan)

        result = serialize_plan(plan)
        result["status"] = "updated"

        return result

    finally:
        db.close()


@router.get(
    "/companies/{company_id}/subscription"
)
def get_company_subscription(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id
                == company_id
            )
            .first()
        )

        if subscription is None:
            return {
                "company_id": company_id,
                "subscription": None,
            }

        plan = (
            db.query(Plan)
            .filter(
                Plan.id
                == subscription.plan_id
            )
            .first()
        )

        return {
            "company_id": company_id,
            "subscription":
                serialize_subscription(
                    subscription,
                    plan,
                ),
        }

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/subscription"
)
def create_subscription(
    company_id: int,
    data: SubscriptionCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        plan = get_plan_or_404(
            db,
            data.plan_id,
            require_enabled=True,
        )

        existing = (
            db.query(Subscription)
            .filter(
                Subscription.company_id
                == company_id
            )
            .first()
        )

        now = datetime.utcnow()

        if existing is not None:

            cycle_reset = (
                existing.plan_id
                != plan.id
                or existing.status
                != "active"
            )

            existing.plan_id = plan.id
            existing.status = "active"

            if cycle_reset:
                existing.started_at = now

            subscription = existing

        else:

            subscription = Subscription(
                company_id=company_id,
                plan_id=plan.id,
                status="active",
                started_at=now,
            )

            db.add(subscription)

        db.commit()
        db.refresh(subscription)

        result = serialize_subscription(
            subscription,
            plan,
        )

        result["status"] = "active"

        return result

    finally:
        db.close()


@router.patch(
    "/companies/{company_id}/subscription"
)
def update_subscription(
    company_id: int,
    data: SubscriptionUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        get_company_or_404(
            db,
            company_id,
        )

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id
                == company_id
            )
            .first()
        )

        if subscription is None:
            raise HTTPException(
                status_code=404,
                detail="Subscription not found",
            )

        cycle_reset = False

        if data.plan_id is not None:

            plan = get_plan_or_404(
                db,
                data.plan_id,
                require_enabled=True,
            )

            if (
                subscription.plan_id
                != plan.id
            ):
                subscription.plan_id = plan.id
                cycle_reset = True

        allowed_statuses = {
            "active",
            "paused",
            "cancelled",
        }

        if data.status is not None:

            status = (
                data.status
                .strip()
                .lower()
            )

            if status not in allowed_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Invalid subscription status"
                    ),
                )

            if (
                status == "active"
                and subscription.status
                != "active"
            ):
                cycle_reset = True

            subscription.status = status

        if cycle_reset:
            subscription.started_at = (
                datetime.utcnow()
            )

        db.commit()
        db.refresh(subscription)

        plan = (
            db.query(Plan)
            .filter(
                Plan.id
                == subscription.plan_id
            )
            .first()
        )

        result = serialize_subscription(
            subscription,
            plan,
        )

        result["status"] = "updated"

        return result

    finally:
        db.close()
