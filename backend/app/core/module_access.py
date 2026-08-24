from fastapi import HTTPException

from backend.app.models.company_module import CompanyModule


def company_module_enabled(db, company_id: int, module_name: str) -> bool:
    item = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id == company_id,
            CompanyModule.module_name == module_name,
            CompanyModule.enabled.is_(True),
        )
        .first()
    )
    return item is not None


def require_company_module(
    db,
    company_id: int,
    module_name: str,
) -> None:
    if not company_module_enabled(db, company_id, module_name):
        raise HTTPException(
            status_code=403,
            detail=f"Company module '{module_name}' is not enabled",
        )
