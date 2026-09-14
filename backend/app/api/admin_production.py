from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.company_lifecycle import (
    CompanyNotFound,
    CompanyNotReady,
    activate_company as activate_company_state,
    deactivate_company as deactivate_company_state,
)
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.readiness import company_readiness
from backend.app.models.user import User
from backend.app.modules.audit.service import audit_service


router = APIRouter(
    prefix="/admin/production",
    tags=["Xvond Admin - Production"],
)


@router.get("/companies/{company_id}/readiness")
def readiness(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        result = company_readiness(db, company_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return result
    finally:
        db.close()


@router.post("/companies/{company_id}/activate")
def activate_company(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    """Compatibility endpoint for the canonical company lifecycle transition.

    AI employee lifecycle is owned exclusively by the Delivery Readiness
    Draft -> Go Live gate. Company activation must never enable employees as a
    side effect. The canonical PATCH /admin/companies/{id}/status endpoint and
    this compatibility route share one lifecycle service.
    """
    db = SessionLocal()
    try:
        try:
            company, result = activate_company_state(db, company_id)
        except CompanyNotFound as exc:
            raise HTTPException(status_code=404, detail="Company not found") from exc
        except CompanyNotReady as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Company is not ready to activate",
                    "issues": exc.readiness["issues"],
                    "agents": exc.readiness["agents"],
                },
            ) from exc

        ready_agent_ids = [
            item["id"]
            for item in result["agents"]
            if item["ready"]
        ]
        audit_service.log(
            db=db,
            action="company.activated",
            resource_type="company",
            resource_id=company.id,
            user_id=current_admin.id,
            company_id=company.id,
            details={
                "source": "legacy_production_endpoint",
                "readiness_status": result.get("status"),
                "ready_agents": ready_agent_ids,
            },
        )
        db.commit()
        return {
            "company_id": company_id,
            "status": "ACTIVE",
            "ready_agents": ready_agent_ids,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/companies/{company_id}/deactivate")
def deactivate_company(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    """Compatibility emergency stop backed by the canonical lifecycle service."""
    db = SessionLocal()
    try:
        try:
            company = deactivate_company_state(db, company_id)
        except CompanyNotFound as exc:
            raise HTTPException(status_code=404, detail="Company not found") from exc
        audit_service.log(
            db=db,
            action="company.deactivated",
            resource_type="company",
            resource_id=company.id,
            user_id=current_admin.id,
            company_id=company.id,
            details={
                "source": "legacy_production_endpoint",
                "emergency_stop": True,
            },
        )
        db.commit()
        return {
            "company_id": company_id,
            "status": "INACTIVE",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
