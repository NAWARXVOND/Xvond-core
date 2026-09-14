from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.module_manager import module_manager
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User
from backend.app.modules.audit.service import audit_service

router = APIRouter(
    prefix="/admin/companies",
    tags=["Xvond Admin - Company Modules"],
)


def get_company(db, company_id: int):
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _module_payload(item: CompanyModule, status: str) -> dict:
    return {
        "id": item.id,
        "company_id": item.company_id,
        "module_name": item.module_name,
        "enabled": item.enabled,
        "status": status,
    }


def _log_module_change(db, admin: User, item: CompanyModule, action: str) -> None:
    audit_service.log(
        db=db,
        action=action,
        resource_type="company_module",
        resource_id=item.id,
        user_id=admin.id,
        company_id=item.company_id,
        details={"module_name": item.module_name, "enabled": item.enabled},
    )


@router.get("/{company_id}/modules")
def list_company_modules(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        get_company(db, company_id)
        modules = (
            db.query(CompanyModule)
            .filter(CompanyModule.company_id == company_id)
            .order_by(CompanyModule.id.asc())
            .all()
        )
        return {
            "company_id": company_id,
            "modules": [
                {
                    "id": item.id,
                    "module_name": item.module_name,
                    "enabled": item.enabled,
                    "installed_at": item.installed_at,
                }
                for item in modules
            ],
        }
    finally:
        db.close()


@router.post("/{company_id}/modules/{module_name}")
def install_company_module(
    company_id: int,
    module_name: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        get_company(db, company_id)
        if module_manager.get(module_name) is None:
            raise HTTPException(status_code=404, detail="Module not found in Xvond Core")

        existing = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id == company_id,
                CompanyModule.module_name == module_name,
            )
            .first()
        )
        if existing is not None:
            if not existing.enabled:
                existing.enabled = True
                _log_module_change(db, current_admin, existing, "company_module.enabled")
                db.commit()
                db.refresh(existing)
                return _module_payload(existing, "enabled")
            return _module_payload(existing, "already_enabled")

        item = CompanyModule(
            company_id=company_id,
            module_name=module_name,
            enabled=True,
        )
        db.add(item)
        db.flush()
        _log_module_change(db, current_admin, item, "company_module.installed")
        db.commit()
        db.refresh(item)
        return _module_payload(item, "installed")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{company_id}/modules/{module_name}/enable")
def enable_company_module(
    company_id: int,
    module_name: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        get_company(db, company_id)
        item = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id == company_id,
                CompanyModule.module_name == module_name,
            )
            .first()
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Company module not installed")
        if not item.enabled:
            item.enabled = True
            _log_module_change(db, current_admin, item, "company_module.enabled")
        db.commit()
        db.refresh(item)
        return _module_payload(item, "enabled")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{company_id}/modules/{module_name}/disable")
def disable_company_module(
    company_id: int,
    module_name: str,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        get_company(db, company_id)
        item = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id == company_id,
                CompanyModule.module_name == module_name,
            )
            .first()
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Company module not installed")
        if item.enabled:
            item.enabled = False
            _log_module_change(db, current_admin, item, "company_module.disabled")
        db.commit()
        db.refresh(item)
        return _module_payload(item, "disabled")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
