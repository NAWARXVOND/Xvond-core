from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.dependencies import (
    require_xvond_admin,
)
from backend.app.core.module_manager import module_manager
from backend.app.models.user import User


router = APIRouter(
    prefix="/admin/modules",
    tags=["Xvond Admin - Modules"],
)


@router.get("/")
def list_core_modules(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    return {
        "modules": module_manager.list_installed()
    }


@router.get("/{module_name}")
def get_core_module(
    module_name: str,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    module = module_manager.get(
        module_name
    )

    if module is None:
        raise HTTPException(
            status_code=404,
            detail="Module not found",
        )

    return {
        "info": module.info(),
        "status": module_manager.status(
            module_name
        ),
    }
