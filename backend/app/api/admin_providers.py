from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel

from backend.app.core.ai.engine import ai_engine
from backend.app.core.ai.provider_policy import require_provider_model
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin

from backend.app.models.company import Company
from backend.app.models.user import User

from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
    CompanyAIProfile,
)


router = APIRouter(
    prefix="/admin/providers",
    tags=["Xvond Admin - AI Providers"],
)


class ProviderCreate(BaseModel):
    name: str
    display_name: str
    priority: int = 100


class ModelCreate(BaseModel):
    provider_name: str
    model_name: str
    display_name: str

    input_price_per_million: Decimal = Decimal("0")
    output_price_per_million: Decimal = Decimal("0")


class CompanyProfileCreate(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None

    allow_fallback: bool = True

    fallback_provider: str | None = None
    fallback_model: str | None = None


@router.get("/runtime")
def runtime_providers(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    return {
        "loaded_providers": (
            ai_engine.list_providers()
        )
    }


@router.post("/")
def create_provider(
    data: ProviderCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        existing = (
            db.query(AIProviderRecord)
            .filter(
                AIProviderRecord.name
                == data.name
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=400,
                detail="Provider already exists",
            )

        provider = AIProviderRecord(
            name=data.name,
            display_name=data.display_name,
            enabled=True,
            priority=data.priority,
        )

        db.add(provider)
        db.commit()
        db.refresh(provider)

        return {
            "id": provider.id,
            "name": provider.name,
            "display_name": provider.display_name,
            "enabled": provider.enabled,
            "status": "created",
        }

    finally:
        db.close()


@router.get("/")
def list_providers(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        providers = (
            db.query(AIProviderRecord)
            .order_by(
                AIProviderRecord.priority.asc()
            )
            .all()
        )

        return {
            "providers": [
                {
                    "id": item.id,
                    "name": item.name,
                    "display_name": item.display_name,
                    "enabled": item.enabled,
                    "priority": item.priority,
                    "runtime_loaded": (
                        item.name
                        in ai_engine.list_providers()
                    ),
                }
                for item in providers
            ]
        }

    finally:
        db.close()


@router.post("/models")
def create_model(
    data: ModelCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        provider = (
            db.query(AIProviderRecord)
            .filter(
                AIProviderRecord.name
                == data.provider_name
            )
            .first()
        )

        if provider is None:
            raise HTTPException(
                status_code=404,
                detail="Provider not found",
            )

        model = AIModelRecord(
            provider_name=data.provider_name,
            model_name=data.model_name,
            display_name=data.display_name,
            input_price_per_million=(
                data.input_price_per_million
            ),
            output_price_per_million=(
                data.output_price_per_million
            ),
            enabled=True,
        )

        db.add(model)
        db.commit()
        db.refresh(model)

        return {
            "id": model.id,
            "provider_name": model.provider_name,
            "model_name": model.model_name,
            "status": "created",
        }

    finally:
        db.close()


@router.get("/models")
def list_models(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:
        models = (
            db.query(AIModelRecord)
            .order_by(
                AIModelRecord.provider_name.asc(),
                AIModelRecord.id.asc(),
            )
            .all()
        )

        return {
            "models": [
                {
                    "id": item.id,
                    "provider_name": item.provider_name,
                    "model_name": item.model_name,
                    "display_name": item.display_name,
                    "input_price_per_million": (
                        item.input_price_per_million
                    ),
                    "output_price_per_million": (
                        item.output_price_per_million
                    ),
                    "enabled": item.enabled,
                }
                for item in models
            ]
        }

    finally:
        db.close()


@router.put(
    "/companies/{company_id}/profile"
)
def update_company_ai_profile(
    company_id: int,
    data: CompanyProfileCreate,
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

        configured_pairs = [
            (
                data.default_provider,
                data.default_model,
                "default",
            ),
            (
                data.fallback_provider,
                data.fallback_model,
                "fallback",
            ),
        ]

        for provider, model, label in configured_pairs:
            if bool(provider) != bool(model):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Both {label} provider and model "
                        "must be configured together"
                    ),
                )
            if provider and model:
                try:
                    require_provider_model(
                        db,
                        provider,
                        model,
                    )
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid {label} provider/model",
                    ) from exc

        profile = (
            db.query(CompanyAIProfile)
            .filter(
                CompanyAIProfile.company_id
                == company_id
            )
            .first()
        )

        if profile is None:
            profile = CompanyAIProfile(
                company_id=company_id
            )

            db.add(profile)

        profile.default_provider = (
            data.default_provider
        )

        profile.default_model = (
            data.default_model
        )

        profile.allow_fallback = (
            data.allow_fallback
        )

        profile.fallback_provider = (
            data.fallback_provider
        )

        profile.fallback_model = (
            data.fallback_model
        )

        db.commit()
        db.refresh(profile)

        return {
            "company_id": company_id,
            "default_provider": (
                profile.default_provider
            ),
            "default_model": (
                profile.default_model
            ),
            "allow_fallback": (
                profile.allow_fallback
            ),
            "fallback_provider": (
                profile.fallback_provider
            ),
            "fallback_model": (
                profile.fallback_model
            ),
            "status": "updated",
        }

    finally:
        db.close()
