from fastapi import (
    Depends,
    HTTPException,
    Request,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from backend.app.core.database.connection import SessionLocal
from backend.app.core.security import decode_access_token_claims
from backend.app.models.company import Company
from backend.app.models.user import User


SESSION_COOKIE_NAME = "xvond_session"
security = HTTPBearer(auto_error=False)


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


def _request_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is not None and credentials.credentials:
        return credentials.credentials
    cookie_token = str(request.cookies.get(SESSION_COOKIE_NAME) or "").strip()
    if cookie_token:
        return cookie_token
    raise HTTPException(status_code=401, detail="Authentication required")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    raw_token = _request_token(request, credentials)
    try:
        claims = decode_access_token_claims(raw_token)
        user_id = int(claims["sub"])
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.active:
        raise HTTPException(status_code=401, detail="User account is inactive")
    if int(claims.get("ver", -1)) != int(user.token_version):
        raise HTTPException(status_code=401, detail="Session has been revoked")

    if user.role in CUSTOMER_ROLES and user.company_id is None:
        raise HTTPException(
            status_code=403,
            detail="Customer user is not attached to a company",
        )

    if user.company_id is not None:
        company = db.query(Company).filter(Company.id == user.company_id).first()
        if company is None:
            raise HTTPException(status_code=403, detail="Company not found")
        if user.role in CUSTOMER_ROLES and not company.active:
            raise HTTPException(status_code=403, detail="Company is inactive")

    return user


def require_customer_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in CUSTOMER_ROLES:
        raise HTTPException(status_code=403, detail="Customer access required")
    return current_user


def require_customer_manager(
    current_user: User = Depends(require_customer_user),
) -> User:
    if current_user.role not in {"owner", "admin", "manager"}:
        raise HTTPException(
            status_code=403,
            detail="Company management access required",
        )
    return current_user


def require_customer_admin(
    current_user: User = Depends(require_customer_user),
) -> User:
    if current_user.role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=403,
            detail="Company owner or admin required",
        )
    return current_user


def require_xvond_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in {"super_admin", "xvond_admin"}:
        raise HTTPException(status_code=403, detail="Xvond admin access required")
    return current_user


def require_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_user
