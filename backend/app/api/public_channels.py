import hmac
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.channels.models import AgentChannel

router = APIRouter(prefix="/channels", tags=["Public Agent Channels"])


class WebsiteChatInput(BaseModel):
    message: str
    conversation_id: int | None = None


class VoiceTurnInput(BaseModel):
    transcript: str
    conversation_id: int | None = None
    session_id: str | None = None


def secure_equal(received: str | None, expected: str | None) -> bool:
    if not received or not expected:
        return False
    return hmac.compare_digest(str(received), str(expected))


def host(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower().strip(".")


def website_origin_allowed(origin: str | None, allowed_domain: str | None) -> bool:
    origin_host = host(origin)
    allowed_host = host(allowed_domain)
    if not origin_host or not allowed_host:
        return False
    return origin_host == allowed_host or origin_host.endswith("." + allowed_host)


def require_channel(db, channel_id: int, channel_type: str) -> AgentChannel:
    channel = db.query(AgentChannel).filter(
        AgentChannel.id == channel_id,
        AgentChannel.channel_type == channel_type,
        AgentChannel.enabled.is_(True),
    ).first()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel unavailable")
    return channel


@router.post("/website/{channel_id}/chat")
def website_chat(
    channel_id: int,
    data: WebsiteChatInput,
    request: Request,
    x_xvond_widget_key: str | None = Header(default=None),
):
    db = SessionLocal()
    try:
        channel = require_channel(db, channel_id, "website")
        config = reveal_config(channel.config)

        if not secure_equal(x_xvond_widget_key, config.get("widget_key")):
            raise HTTPException(status_code=401, detail="Invalid widget key")

        if not website_origin_allowed(
            request.headers.get("origin"),
            config.get("allowed_domain"),
        ):
            raise HTTPException(status_code=403, detail="Website origin is not allowed")

        return agent_runtime.chat(
            db=db,
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            message=data.message,
            conversation_id=data.conversation_id,
        )
    finally:
        db.close()


@router.post("/voice/{channel_id}/turn")
def voice_turn(
    channel_id: int,
    data: VoiceTurnInput,
    x_xvond_voice_token: str | None = Header(default=None),
):
    """Provider-neutral voice gateway.

    A telephony/STT adapter sends the caller transcript here and receives the
    agent response text for TTS playback. Provider-specific call control stays
    in the adapter while Xvond owns the business AI and conversation state.
    """
    db = SessionLocal()
    try:
        channel = require_channel(db, channel_id, "voice")
        config = reveal_config(channel.config)
        if not secure_equal(x_xvond_voice_token, config.get("auth_token")):
            raise HTTPException(status_code=401, detail="Invalid voice channel token")

        result = agent_runtime.chat(
            db=db,
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            message=data.transcript,
            conversation_id=data.conversation_id,
        )
        return {
            "channel_id": channel.id,
            "session_id": data.session_id,
            "conversation_id": result["conversation_id"],
            "text": result["response"]["content"],
        }
    finally:
        db.close()
