from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(
    prefix="/customer/business",
    tags=["Customer Human Handoffs"],
)


def company_id_for(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(status_code=403, detail="Customer company required")
    return user.company_id


@router.get("/handoffs")
def handoffs(current_user: User = Depends(require_customer_manager)):
    """Human handoffs remain a separate concern.

    Real customer work is exposed through /customer/action-requests. The former
    fixed leads/bookings/orders endpoints were removed so the customer portal
    follows the same generic Operations model used by AI employees and admin.
    """
    db = SessionLocal()
    try:
        company_id = company_id_for(current_user)
        return db.query(HumanHandoff).filter(
            HumanHandoff.company_id == company_id
        ).order_by(HumanHandoff.id.desc()).all()
    finally:
        db.close()
