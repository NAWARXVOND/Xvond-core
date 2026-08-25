from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.database.connection import SessionLocal
from backend.app.core.security import (
    create_access_token,
    verify_password,
)
from backend.app.models.user import User
from backend.app.models.company import Company


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(
    data: LoginRequest,
):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(
                User.email
                == data.email.strip().lower()
            )
            .first()
        )

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        if not user.active:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        if not verify_password(
            data.password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        if user.company_id is not None:

            company = (
                db.query(Company)
                .filter(
                    Company.id
                    == user.company_id
                )
                .first()
            )

            if (
                company is None
                or not company.active
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Company is inactive",
                )

        token = create_access_token(
            user.id,
            user.token_version,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "company_id": user.company_id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
            },
        }

    finally:
        db.close()



# ============================================================
# CUSTOMER PASSWORD SECURITY
# ============================================================

from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from fastapi import Depends

from backend.app.core.config.settings import settings
from backend.app.core.dependencies import get_current_user
from backend.app.core.mail import send_password_reset_code
from backend.app.core.security import hash_password
from backend.app.models.password_reset import PasswordResetCode


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _validate_new_password(
    password: str,
):
    if len(password) < 10:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least "
                "10 characters"
            ),
        )

    if not any(
        c.isalpha()
        for c in password
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain a letter"
            ),
        )

    if not any(
        c.isdigit()
        for c in password
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain a number"
            ),
        )


def _hash_reset_code(
    email: str,
    code: str,
) -> str:

    message = (
        email.lower().strip()
        + ":"
        + code
    ).encode("utf-8")

    return hmac.new(
        settings.JWT_SECRET.encode(
            "utf-8"
        ),
        message,
        hashlib.sha256,
    ).hexdigest()


@router.post(
    "/customer/forgot-password"
)
def customer_forgot_password(
    data: ForgotPasswordRequest,
):
    db = SessionLocal()

    generic_response = {
        "status": "accepted",
        "message": (
            "If the email belongs to a "
            "customer account, a verification "
            "code will be sent."
        ),
    }

    try:
        email = (
            data.email
            .strip()
            .lower()
        )

        user = (
            db.query(User)
            .filter(
                User.email == email
            )
            .first()
        )

        # Do not expose whether an account exists.
        # Also: no password-reset flow for Xvond admins.
        if (
            user is None
            or user.company_id is None
            or user.role
            in (
                "super_admin",
                "xvond_admin",
            )
        ):
            return generic_response

        latest = (
            db.query(
                PasswordResetCode
            )
            .filter(
                PasswordResetCode.user_id
                == user.id,
                PasswordResetCode.used_at
                .is_(None),
            )
            .order_by(
                PasswordResetCode.id.desc()
            )
            .first()
        )

        now = datetime.utcnow()

        if (
            latest is not None
            and (
                now
                - latest.created_at
            ).total_seconds()
            < 60
        ):
            return generic_response

        # Invalidate older codes.
        old_codes = (
            db.query(
                PasswordResetCode
            )
            .filter(
                PasswordResetCode.user_id
                == user.id,
                PasswordResetCode.used_at
                .is_(None),
            )
            .all()
        )

        for item in old_codes:
            item.used_at = now

        code = (
            f"{secrets.randbelow(1000000):06d}"
        )

        reset = PasswordResetCode(
            user_id=user.id,
            email=email,
            code_hash=_hash_reset_code(
                email,
                code,
            ),
            attempts=0,
            expires_at=(
                now
                + timedelta(
                    minutes=10
                )
            ),
        )

        db.add(reset)
        db.commit()

        try:
            send_password_reset_code(
                email,
                code,
            )

        except Exception:
            # Do not leave a usable OTP when
            # email delivery failed.
            reset.used_at = datetime.utcnow()
            db.commit()

            raise HTTPException(
                status_code=503,
                detail=(
                    "Email service is unavailable"
                ),
            )

        return generic_response

    finally:
        db.close()


@router.post(
    "/customer/reset-password"
)
def customer_reset_password(
    data: ResetPasswordRequest,
):
    _validate_new_password(
        data.new_password
    )

    db = SessionLocal()

    try:
        email = (
            data.email
            .strip()
            .lower()
        )

        user = (
            db.query(User)
            .filter(
                User.email == email
            )
            .first()
        )

        if (
            user is None
            or user.company_id is None
            or user.role
            in (
                "super_admin",
                "xvond_admin",
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid or expired code"
                ),
            )

        reset = (
            db.query(
                PasswordResetCode
            )
            .filter(
                PasswordResetCode.user_id
                == user.id,
                PasswordResetCode.used_at
                .is_(None),
            )
            .order_by(
                PasswordResetCode.id.desc()
            )
            .first()
        )

        now = datetime.utcnow()

        if (
            reset is None
            or reset.expires_at < now
            or reset.attempts >= 5
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid or expired code"
                ),
            )

        reset.attempts += 1

        expected = _hash_reset_code(
            email,
            data.code.strip(),
        )

        if not hmac.compare_digest(
            expected,
            reset.code_hash,
        ):
            db.commit()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid or expired code"
                ),
            )

        user.password_hash = (
            hash_password(
                data.new_password
            )
        )
        user.token_version += 1

        reset.used_at = now

        db.commit()

        return {
            "status":
                "password_changed",
        }

    finally:
        db.close()


@router.post(
    "/customer/change-password"
)
def customer_change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(
        get_current_user
    ),
):
    if (
        current_user.company_id
        is None
        or current_user.role
        in (
            "super_admin",
            "xvond_admin",
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Customer account required"
            ),
        )

    _validate_new_password(
        data.new_password
    )

    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail=(
                "New password must be "
                "different"
            ),
        )

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(
                User.id
                == current_user.id
            )
            .first()
        )

        if (
            user is None
            or not verify_password(
                data.current_password,
                user.password_hash,
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Current password is incorrect"
                ),
            )

        user.password_hash = (
            hash_password(
                data.new_password
            )
        )
        user.token_version += 1

        db.commit()

        return {
            "status":
                "password_changed",
        }

    finally:
        db.close()


@router.post("/logout")
def logout(
    current_user: User = Depends(
        get_current_user
    ),
):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.id == current_user.id)
            .first()
        )

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="User not found",
            )

        user.token_version += 1
        db.commit()

        return {
            "status": "logged_out",
        }
    finally:
        db.close()
