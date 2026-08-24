
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
)

from backend.app.models.user import User

from backend.app.modules.ai_agent.models import (
    AIAgent,
)

from backend.app.modules.billing.limits import (
    limits_service,
)

from backend.app.modules.channels.models import (
    AgentChannel,
)

from backend.app.modules.channels.catalog import (
    get_channel_definition,
    validate_channel_config,
)


router = APIRouter(
    prefix="/admin/channels",
    tags=["Xvond Admin - Channels"],
)


class ChannelCreate(BaseModel):
    channel_type: str
    config: dict = Field(
        default_factory=dict
    )


class ChannelUpdate(BaseModel):
    config: dict | None = None
    enabled: bool | None = None


class WhatsAppConfigUpdate(BaseModel):
    phone_number_id: str
    access_token: str
    verify_token: str
    app_secret: str
    graph_api_version: str = "v23.0"


def _channel_configured(
    channel: AgentChannel,
) -> bool:

    try:
        validate_channel_config(
            channel.channel_type,
            channel.config or {},
        )
        return True

    except ValueError:
        return False


def serialize_channel(
    channel: AgentChannel,
) -> dict:

    return {
        "id": channel.id,
        "company_id": channel.company_id,
        "agent_id": channel.agent_id,
        "channel_type": channel.channel_type,

        # Never expose credentials.
        "config": public_config(
            channel.config
        ),

        "configured_secret_fields":
            configured_secret_fields(
                channel.config
            ),

        "configured": (
            _channel_configured(
                channel
            )
        ),

        "enabled": channel.enabled,
        "created_at": channel.created_at,
    }


@router.post("/agents/{agent_id}")
def create_channel(
    agent_id: int,
    data: ChannelCreate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == agent_id
            )
            .first()
        )

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="AI Agent not found",
            )

        channel_type = (
            data.channel_type
            .strip()
            .lower()
        )

        if not channel_type:
            raise HTTPException(
                status_code=400,
                detail="Channel type is required",
            )

        if (
            get_channel_definition(
                channel_type
            )
            is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported channel type"
                ),
            )

        # One channel type per agent.
        # Prevents duplicate WhatsApp,
        # Website, Voice, etc.
        existing = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.agent_id
                == agent.id,
                AgentChannel.channel_type
                == channel_type,
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This channel type is "
                    "already assigned to the agent"
                ),
            )

        limits_service.check_channel_limit(
            db,
            agent.company_id,
        )

        channel = AgentChannel(
            company_id=agent.company_id,
            agent_id=agent.id,
            channel_type=
                channel_type,
            config=data.config,
            enabled=True,
        )

        db.add(channel)
        db.commit()
        db.refresh(channel)

        result = serialize_channel(
            channel
        )

        result["status"] = "created"

        return result

    finally:
        db.close()


@router.get("/companies/{company_id}")
def list_company_channels(
    company_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        items = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id
                == company_id
            )
            .order_by(
                AgentChannel.id.asc()
            )
            .all()
        )

        return {
            "company_id": company_id,
            "channels": [
                serialize_channel(item)
                for item in items
            ],
        }

    finally:
        db.close()


@router.put("/{channel_id}")
def update_channel(
    channel_id: int,
    data: ChannelUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.id
                == channel_id
            )
            .first()
        )

        if channel is None:
            raise HTTPException(
                status_code=404,
                detail="Channel not found",
            )

        # Only check limit when changing
        # disabled -> enabled.
        if (
            data.enabled is True
            and channel.enabled is False
        ):
            limits_service.check_channel_limit(
                db,
                channel.company_id,
            )

        if data.config is not None:
            channel.config = merge_config(
                channel.config,
                data.config,
            )

        if data.enabled is not None:
            channel.enabled = data.enabled

        db.commit()
        db.refresh(channel)

        result = serialize_channel(
            channel
        )

        result["status"] = "updated"

        return result

    finally:
        db.close()


@router.put(
    "/{channel_id}/whatsapp-config"
)
def configure_whatsapp(
    channel_id: int,
    data: WhatsAppConfigUpdate,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.id
                == channel_id,
                AgentChannel.channel_type
                == "whatsapp",
            )
            .first()
        )

        if channel is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "WhatsApp channel "
                    "not found"
                ),
            )

        new_config = merge_config(
            channel.config,
            {
                "phone_number_id":
                    data.phone_number_id,

                "access_token":
                    data.access_token,

                "verify_token":
                    data.verify_token,

                "app_secret":
                    data.app_secret,

                "graph_api_version":
                    data.graph_api_version,
            },
        )

        try:
            validate_channel_config(
                "whatsapp",
                new_config,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

        channel.config = new_config
        channel.enabled = True

        db.commit()
        db.refresh(channel)

        result = serialize_channel(
            channel
        )

        result["status"] = "configured"

        return result

    finally:
        db.close()


@router.delete("/{channel_id}")
def delete_channel(
    channel_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):
    db = SessionLocal()

    try:

        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.id
                == channel_id
            )
            .first()
        )

        if channel is None:
            raise HTTPException(
                status_code=404,
                detail="Channel not found",
            )

        db.delete(channel)
        db.commit()

        return {
            "channel_id": channel_id,
            "status": "deleted",
        }

    finally:
        db.close()
