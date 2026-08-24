from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.module_manager import module_manager

from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.models.user import User


router = APIRouter(
    prefix="/admin/companies",
    tags=["Xvond Admin - Company Modules"],
)


def get_company(
    db,
    company_id: int,
):
    company = (
        db.query(Company)
        .filter(
            Company.id == company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return company


@router.get("/{company_id}/modules")
def list_company_modules(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        modules = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id
                == company_id
            )
            .order_by(
                CompanyModule.id.asc()
            )
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


@router.post(
    "/{company_id}/modules/{module_name}"
)
def install_company_module(
    company_id: int,
    module_name: str,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        core_module = module_manager.get(
            module_name
        )

        if core_module is None:
            raise HTTPException(
                status_code=404,
                detail="Module not found in Xvond Core",
            )

        existing = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id
                == company_id,
                CompanyModule.module_name
                == module_name,
            )
            .first()
        )

        if existing is not None:
            if not existing.enabled:
                existing.enabled = True
                db.commit()
                db.refresh(existing)

            return {
                "id": existing.id,
                "company_id": existing.company_id,
                "module_name": existing.module_name,
                "enabled": existing.enabled,
                "status": "already_enabled",
            }

        item = CompanyModule(
            company_id=company_id,
            module_name=module_name,
            enabled=True,
        )

        db.add(item)
        db.commit()
        db.refresh(item)

        return {
            "id": item.id,
            "company_id": item.company_id,
            "module_name": item.module_name,
            "enabled": item.enabled,
            "status": "installed",
        }

    finally:
        db.close()


@router.post(
    "/{company_id}/modules/{module_name}/enable"
)
def enable_company_module(
    company_id: int,
    module_name: str,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        item = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id
                == company_id,
                CompanyModule.module_name
                == module_name,
            )
            .first()
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Company module not installed",
            )

        item.enabled = True

        db.commit()
        db.refresh(item)

        return {
            "id": item.id,
            "company_id": item.company_id,
            "module_name": item.module_name,
            "enabled": item.enabled,
            "status": "enabled",
        }

    finally:
        db.close()


@router.post(
    "/{company_id}/modules/{module_name}/disable"
)
def disable_company_module(
    company_id: int,
    module_name: str,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        get_company(
            db,
            company_id,
        )

        item = (
            db.query(CompanyModule)
            .filter(
                CompanyModule.company_id
                == company_id,
                CompanyModule.module_name
                == module_name,
            )
            .first()
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Company module not installed",
            )

        item.enabled = False

        db.commit()
        db.refresh(item)

        return {
            "id": item.id,
            "company_id": item.company_id,
            "module_name": item.module_name,
            "enabled": item.enabled,
            "status": "disabled",
        }

    finally:
        db.close()
