from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.admin_delivery_readiness import router as delivery_readiness_router
from backend.app.core.config.settings import settings
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.n8n_gateway import n8n_gateway
from backend.app.core.password_policy import validate_password
from backend.app.core.readiness import company_readiness
from backend.app.core.security import hash_password
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.billing.models import Plan, Subscription

router = APIRouter(prefix="/admin", tags=["Xvond Admin"])
router.include_router(delivery_readiness_router)


class CompanyCreate(BaseModel):
    name: str
    owner_email: str
    owner_full_name: str
    owner_password: str


class CompanyStatusUpdate(BaseModel):
    active: bool


@router.get("/workflow-engine/status")
def workflow_engine_status(current_admin: User = Depends(require_xvond_admin)):
    enabled = bool(settings.N8N_ENABLED)
    configured = bool(n8n_gateway.configured())
    if configured:
        status = "ready"
    elif enabled:
        status = "needs_setup"
    else:
        status = "disabled"
    return {
        "status": status,
        "enabled": enabled,
        "configured": configured,
        "webhook_configured": bool(settings.N8N_WEBHOOK_URL),
        "authentication_configured": bool(settings.N8N_SHARED_SECRET),
        "timeout_seconds": settings.N8N_TIMEOUT_SECONDS,
        "max_retries": settings.N8N_MAX_RETRIES,
    }


@router.post("/companies")
def create_company(data: CompanyCreate, current_admin: User = Depends(require_xvond_admin)):
    name = data.name.strip()
    owner_email = data.owner_email.strip().lower()
    owner_full_name = data.owner_full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name is required")
    if not owner_email:
        raise HTTPException(status_code=400, detail="Owner email is required")
    if not owner_full_name:
        raise HTTPException(status_code=400, detail="Owner full name is required")
    try:
        validate_password(data.owner_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == owner_email).first()
        if existing_user is not None:
            raise HTTPException(status_code=400, detail="Owner email already exists")
        company = Company(name=name, active=False)
        db.add(company)
        db.flush()
        owner = User(
            company_id=company.id,
            email=owner_email,
            full_name=owner_full_name,
            password_hash=hash_password(data.owner_password),
            role="owner",
        )
        db.add(owner)
        db.add(CompanyModule(company_id=company.id, module_name="ai_agent", enabled=True))
        onboarding_plan = (
            db.query(Plan)
            .filter(Plan.name == "Onboarding", Plan.enabled.is_(True))
            .first()
        )
        if onboarding_plan is not None:
            db.add(Subscription(company_id=company.id, plan_id=onboarding_plan.id, status="active"))
        db.commit()
        db.refresh(company)
        db.refresh(owner)
        return {
            "company": {"id": company.id, "name": company.name, "active": company.active},
            "owner": {
                "id": owner.id,
                "company_id": owner.company_id,
                "email": owner.email,
                "full_name": owner.full_name,
                "role": owner.role,
            },
            "status": "created",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/companies/{company_id}/status")
def update_company_status(
    company_id: int,
    data: CompanyStatusUpdate,
    current_admin: User = Depends(require_xvond_admin),
):
    """Canonical company lifecycle switch.

    Activation is readiness-gated. Deactivation is an emergency stop and disables
    every AI employee; employees must pass their own Go Live gate again later.
    """
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        if data.active:
            readiness = company_readiness(db, company_id)
            if readiness is None:
                raise HTTPException(status_code=404, detail="Company not found")
            if not readiness["ready"]:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Company is not ready to activate",
                        "issues": readiness["issues"],
                        "agents": readiness["agents"],
                    },
                )
            company.active = True
        else:
            company.active = False
            (
                db.query(AIAgent)
                .filter(AIAgent.company_id == company_id)
                .update({AIAgent.enabled: False}, synchronize_session=False)
            )

        db.commit()
        db.refresh(company)
        return {
            "status": "updated",
            "company": {"id": company.id, "name": company.name, "active": company.active},
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/companies")
def list_companies(current_admin: User = Depends(require_xvond_admin)):
    db = SessionLocal()
    try:
        companies = db.query(Company).order_by(Company.id.asc()).all()
        return {
            "companies": [
                {
                    "id": company.id,
                    "name": company.name,
                    "active": company.active,
                    "created_at": company.created_at,
                }
                for company in companies
            ]
        }
    finally:
        db.close()
