from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import (
    get_current_user,
    require_customer_admin,
)
from backend.app.core.security import hash_password
from backend.app.core.password_policy import validate_password
from backend.app.models.user import User


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


class EmployeeCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "employee"


@router.get("/me")
def me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "company_id": current_user.company_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "active": current_user.active,
    }


@router.post("/")
def create_company_user(
    data: EmployeeCreate,
    current_user: User = Depends(
        require_customer_admin
    ),
):
    if current_user.company_id is None:
        raise HTTPException(
            status_code=400,
            detail="User is not attached to a company",
        )

    if data.role not in {
        "admin",
        "manager",
        "employee",
    }:
        raise HTTPException(
            status_code=400,
            detail="Invalid company role",
        )

    email = (
        data.email
        .strip()
        .lower()
    )

    full_name = (
        data.full_name
        .strip()
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required",
        )

    if not full_name:
        raise HTTPException(
            status_code=400,
            detail="Full name is required",
        )

    try:
        validate_password(
            data.password
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    db = SessionLocal()

    try:
        existing = (
            db.query(User)
            .filter(
                User.email == email
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=400,
                detail="Email already exists",
            )

        user = User(
            company_id=current_user.company_id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(
                data.password
            ),
            role=data.role,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "id": user.id,
            "company_id": user.company_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "active": user.active,
            "status": "created",
        }

    finally:
        db.close()


class UserStatusUpdate(BaseModel):
    active: bool


@router.patch("/{user_id}/status")
def update_company_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: User = Depends(
        require_customer_admin
    ),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot disable your own account",
        )

    db = SessionLocal()

    try:
        target = (
            db.query(User)
            .filter(
                User.id == user_id,
                User.company_id == current_user.company_id,
            )
            .first()
        )

        if target is None:
            raise HTTPException(
                status_code=404,
                detail="Company user not found",
            )

        if target.role == "owner":
            raise HTTPException(
                status_code=403,
                detail="The company owner cannot be disabled",
            )

        if (
            target.role == "admin"
            and current_user.role != "owner"
        ):
            raise HTTPException(
                status_code=403,
                detail="Only the owner can manage administrators",
            )

        target.active = data.active

        if not data.active:
            target.token_version += 1

        db.commit()

        return {
            "id": target.id,
            "active": target.active,
            "status": (
                "activated"
                if target.active
                else "deactivated"
            ),
        }
    finally:
        db.close()
