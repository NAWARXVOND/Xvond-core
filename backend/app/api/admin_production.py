from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.readiness import company_readiness

from backend.app.models.company import Company
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent


router = APIRouter(
    prefix="/admin/production",
    tags=["Xvond Admin - Production"],
)


@router.get(
    "/companies/{company_id}/readiness"
)
def readiness(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        result = company_readiness(
            db,
            company_id,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Company not found",
            )

        return result

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/activate"
)
def activate_company(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    """Activate only the company production state.

    AI employee lifecycle is owned exclusively by the Delivery Readiness
    Draft -> Go Live gate. This endpoint must never enable employees as a side
    effect, otherwise production activation could bypass employee readiness,
    package capacity, and channel lifecycle checks.
    """
    db = SessionLocal()

    try:
        result = company_readiness(
            db,
            company_id,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Company not found",
            )

        if not result["ready"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message":
                        "Company is not production ready",
                    "issues":
                        result["issues"],
                    "agents":
                        result["agents"],
                },
            )

        company = (
            db.query(Company)
            .filter(
                Company.id == company_id
            )
            .first()
        )

        company.active = True

        ready_agent_ids = [
            item["id"]
            for item in result["agents"]
            if item["ready"]
        ]

        db.commit()

        return {
            "company_id": company_id,
            "status": "ACTIVE",
            "ready_agents": ready_agent_ids,
        }

    finally:
        db.close()


@router.post(
    "/companies/{company_id}/deactivate"
)
def deactivate_company(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    """Emergency company stop: disable the company and all AI employees.

    Re-enabling employees still requires the normal Delivery Readiness Go Live
    flow, so a company-level stop cannot be undone by this legacy endpoint.
    """
    db = SessionLocal()

    try:

        company = (
            db.query(Company)
            .filter(
                Company.id
                == company_id
            )
            .first()
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail="Company not found",
            )

        company.active = False

        (
            db.query(AIAgent)
            .filter(
                AIAgent.company_id
                == company_id
            )
            .update(
                {
                    AIAgent.enabled:
                        False
                },
                synchronize_session=False,
            )
        )

        db.commit()

        return {
            "company_id":
                company_id,
            "status":
                "INACTIVE",
        }

    finally:
        db.close()
