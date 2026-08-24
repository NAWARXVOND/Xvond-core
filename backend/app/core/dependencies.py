
from fastapi import (
    Depends,
    HTTPException,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.security import (
    decode_access_token,
)
from backend.app.models.company import Company
from backend.app.models.user import User


security = HTTPBearer()


XVOND_INTERNAL_ROLES = {
    "super_admin",
    "xvond_admin",
    "developer",
    "support",
}


CUSTOMER_ROLES = {
    "owner",
    "admin",
    "manager",
    "employee",
}


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
    db: Session = Depends(get_db),
) -> User:

    try:

        user_id = decode_access_token(
            credentials.credentials
        )

    except Exception:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    if (
        user.role in CUSTOMER_ROLES
        and user.company_id is None
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Customer user is not attached "
                "to a company"
            ),
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

        if company is None:
            raise HTTPException(
                status_code=403,
                detail="Company not found",
            )

        if (
            user.role in CUSTOMER_ROLES
            and not company.active
        ):
            raise HTTPException(
                status_code=403,
                detail="Company is inactive",
            )

    return user


def require_customer_user(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:

    if (
        current_user.role
        not in CUSTOMER_ROLES
    ):
        raise HTTPException(
            status_code=403,
            detail="Customer access required",
        )

    return current_user


def require_customer_manager(
    current_user: User = Depends(
        require_customer_user
    ),
) -> User:

    if current_user.role not in {
        "owner",
        "admin",
        "manager",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Company management access required"
            ),
        )

    return current_user


def require_customer_admin(
    current_user: User = Depends(
        require_customer_user
    ),
) -> User:

    if current_user.role not in {
        "owner",
        "admin",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Company owner or admin required"
            ),
        )

    return current_user


def require_xvond_admin(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:

    if current_user.role not in {
        "super_admin",
        "xvond_admin",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Xvond admin access required"
            ),
        )

    return current_user


def require_super_admin(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:

    if (
        current_user.role
        != "super_admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Super admin access required"
            ),
        )

    return current_user
