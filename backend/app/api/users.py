from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import get_current_user, require_customer_manager
from backend.app.core.security import hash_password
from backend.app.core.password_policy import validate_password
from backend.app.models.user import User


router = APIRouter(prefix="/users", tags=["Users"])


class EmployeeCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "employee"


class UserStatusUpdate(BaseModel):
    active: bool


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "company_id": user.company_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _serialize(current_user)


@router.get("/")
def list_company_users(current_user: User = Depends(require_customer_manager)):
    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(User.company_id == current_user.company_id)
            .order_by(User.id.asc())
            .all()
        )
        return {"users": [_serialize(user) for user in users]}
    finally:
        db.close()


@router.post("/")
def create_company_user(
    data: EmployeeCreate,
    current_user: User = Depends(require_customer_manager),
):
    role = data.role.strip().lower()
    if role not in {"manager", "employee"}:
        raise HTTPException(400, "Only Staff or Manager accounts can be created here")

    email = data.email.strip().lower()
    full_name = data.full_name.strip()
    if not email or not full_name:
        raise HTTPException(400, "Email and full name are required")
    try:
        validate_password(data.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first() is not None:
            raise HTTPException(409, "Email already exists")
        user = User(
            company_id=current_user.company_id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(data.password),
            role=role,
            active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        result = _serialize(user)
        result["status"] = "created"
        return result
    finally:
        db.close()


@router.patch("/{user_id}/status")
def update_company_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: User = Depends(require_customer_manager),
):
    if user_id == current_user.id:
        raise HTTPException(400, "You cannot disable your own account")

    db = SessionLocal()
    try:
        target = (
            db.query(User)
            .filter(User.id == user_id, User.company_id == current_user.company_id)
            .first()
        )
        if target is None:
            raise HTTPException(404, "Company user not found")
        if target.role in {"owner", "admin"}:
            raise HTTPException(403, "This protected management account cannot be changed here")
        target.active = data.active
        if not data.active:
            target.token_version += 1
        db.commit()
        result = _serialize(target)
        result["status"] = "activated" if target.active else "deactivated"
        return result
    finally:
        db.close()
