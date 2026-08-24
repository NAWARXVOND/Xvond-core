
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field

from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.core.config_secrets import (
    configured_secret_fields,
    merge_config,
    public_config,
    reveal_config,
)

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.integrations.catalog import (
    validate_integration_config,
)
from backend.app.modules.integrations.models import (
    CompanyIntegration,
)


router = APIRouter(
    prefix="/admin/integrations",
    tags=["Xvond Admin - Integrations"],
)


class IntegrationCreate(BaseModel):
    integration_type: str
    name: str
    config: dict = Field(
        default_factory=dict
    )


class IntegrationUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None


def _integration_configured(item: CompanyIntegration) -> bool:
    try:
        validate_integration_config(
            item.integration_type,
            reveal_config(item.config),
        )
        return True
    except ValueError:
        return False


def serialize_integration(
    item: CompanyIntegration,
) -> dict:

    return {
        "id": item.id,
        "company_id": item.company_id,
        "integration_type":
            item.integration_type,
        "name": item.name,

        # Secrets never leave backend.
        "config": public_config(
            item.config
        ),

        "configured_secret_fields":
            configured_secret_fields(
                item.config
            ),

        "configured": _integration_configured(item),

        "enabled": item.enabled,
        "created_at": item.created_at,
    }


@router.post("/companies/{company_id}")
def create_integration(
    company_id: int,
    data: IntegrationCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

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

        integration = CompanyIntegration(
            company_id=company_id,
            integration_type=
                data.integration_type
                .strip()
                .lower(),
            name=data.name.strip(),
            config=data.config,
            enabled=True,
        )

        db.add(integration)
        db.commit()
        db.refresh(integration)

        result = serialize_integration(
            integration
        )

        result["status"] = "created"

        return result

    finally:
        db.close()


@router.get("/companies/{company_id}")
def list_company_integrations(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

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

        items = (
            db.query(CompanyIntegration)
            .filter(
                CompanyIntegration.company_id
                == company_id
            )
            .order_by(
                CompanyIntegration.id.asc()
            )
            .all()
        )

        return {
            "company_id": company_id,
            "integrations": [
                serialize_integration(item)
                for item in items
            ],
        }

    finally:
        db.close()


@router.patch("/{integration_id}")
def update_integration(
    integration_id: int,
    data: IntegrationUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        item = (
            db.query(CompanyIntegration)
            .filter(
                CompanyIntegration.id
                == integration_id
            )
            .first()
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Integration not found",
            )

        if data.name is not None:

            name = data.name.strip()

            if not name:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Integration name "
                        "cannot be empty"
                    ),
                )

            item.name = name

        if data.config is not None:
            item.config = merge_config(
                item.config,
                data.config,
            )

        if data.enabled is not None:
            item.enabled = data.enabled

        db.commit()
        db.refresh(item)

        result = serialize_integration(
            item
        )

        result["status"] = "updated"

        return result

    finally:
        db.close()


@router.delete("/{integration_id}")
def delete_integration(
    integration_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        item = (
            db.query(CompanyIntegration)
            .filter(
                CompanyIntegration.id
                == integration_id
            )
            .first()
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Integration not found",
            )

        db.delete(item)
        db.commit()

        return {
            "integration_id":
                integration_id,
            "status": "deleted",
        }

    finally:
        db.close()
