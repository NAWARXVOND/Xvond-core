from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.password_policy import validate_password
from backend.app.core.security import hash_password
from backend.app.models.company import Company
from backend.app.models.user import User

router = APIRouter(prefix="/admin/company-users", tags=["Xvond Admin - Company Users"])

ALLOWED_ROLES = {"owner", "admin", "manager", "employee"}


class CompanyUserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "employee"


class CompanyUserStatusUpdate(BaseModel):
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


@router.get("/companies/{company_id}")
def list_company_users(company_id: int, current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(404, "Company not found")
        users = db.query(User).filter(User.company_id == company_id).order_by(User.id.asc()).all()
        return {"company_id": company_id, "users": [_serialize(user) for user in users]}
    finally:
        db.close()


@router.post("/companies/{company_id}")
def create_company_user(
    company_id: int,
    data: CompanyUserCreate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(404, "Company not found")
        email = data.email.strip().lower()
        full_name = data.full_name.strip()
        role = data.role.strip().lower()
        if not email or not full_name:
            raise HTTPException(400, "Email and full name are required")
        if role not in ALLOWED_ROLES:
            raise HTTPException(400, "Invalid company role")
        if db.query(User).filter(User.email == email).first() is not None:
            raise HTTPException(409, "Email already exists")
        try:
            validate_password(data.password)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if role == "owner" and db.query(User).filter(User.company_id == company_id, User.role == "owner").first() is not None:
            raise HTTPException(409, "This company already has an owner")
        user = User(
            company_id=company_id,
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
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{user_id}/status")
def update_company_user_status(
    user_id: int,
    data: CompanyUserStatusUpdate,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.company_id.isnot(None)).first()
        if user is None:
            raise HTTPException(404, "Company user not found")
        if user.role == "owner" and data.active is False:
            raise HTTPException(409, "Company owner cannot be disabled")
        user.active = data.active
        if not data.active:
            user.token_version += 1
        db.commit()
        result = _serialize(user)
        result["status"] = "activated" if user.active else "deactivated"
        return result
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()
