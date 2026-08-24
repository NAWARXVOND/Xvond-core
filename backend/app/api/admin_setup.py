from fastapi import APIRouter, Depends

from backend.app.core.dependencies import (
    require_xvond_admin,
)
from backend.app.models.user import User

from backend.app.modules.channels.catalog import (
    list_channel_definitions,
)

from backend.app.modules.integrations.catalog import (
    list_integration_definitions,
)


router = APIRouter(
    prefix="/admin/setup",
    tags=["Xvond Admin - Setup"],
)


@router.get("/catalog")
def setup_catalog(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    return {
        "channels": list_channel_definitions(),
        "integrations":
            list_integration_definitions(),
    }
