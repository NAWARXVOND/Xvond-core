import hmac
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.api.website_widget import website_behavior
from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.visitor_tokens import (
    VisitorTokenError,
    issue_website_visitor_token,
    verify_website_visitor_token,
)
from backend.app.modules.ai_agent.models import AIConversation, AIMessage
from backend.app.modules.channels.conversation_source import bind_conversation_source
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.tools.business_models import HumanHandoff

router = APIRouter(prefix="/channels", tags=["Public Agent Channels"])


class WebsiteChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: int | None = None


class VoiceTurnInput(BaseModel):
    transcript: str = Field(min_length=1, max_length=12000)
    conversation_id: int | None = None
    session_id: str | None = None


ACTIVE_HANDOFF_STATUSES = {"pending", "in_progress"}


def secure_equal(received, expected):
    return bool(
        received
        and expected
        and hmac.compare_digest(str(received), str(expected))
    )


def host(value):
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower().strip(".")


def website_origin_allowed(origin, allowed_domain):
    origin_host = host(origin)
    allowed_host = host(allowed_domain)
    return bool(
        origin_host
        and allowed_host
        and (
            origin_host == allowed_host
            or origin_host.endswith("." + allowed_host)
        )
    )


def require_channel(db, channel_id, channel_type):
    channel = (
        db.query(AgentChannel)
        .filter(
            AgentChannel.id == channel_id,
            AgentChannel.channel_type == channel_type,
            AgentChannel.enabled.is_(True),
        )
        .first()
    )
    if channel is None:
        raise HTTPException(404, "Channel unavailable")
    return channel


def _website_auth(db, channel_id, request, key):
    channel = require_channel(db, channel_id, "website")
    config = reveal_config(channel.config) or {}
    if not secure_equal(key, config.get("widget_key")):
        raise HTTPException(401, "Invalid widget key")
    if not website_origin_allowed(
        request.headers.get("origin"), config.get("allowed_domain")
    ):
        raise HTTPException(403, "Website origin is not allowed")
    return channel, config


def _require_visitor_token(token, channel_id: int, conversation_id: int):
    try:
        return verify_website_visitor_token(
            token,
            channel_id=channel_id,
            conversation_id=conversation_id,
        )
    except VisitorTokenError as exc:
        raise HTTPException(401, str(exc)) from exc


def _human_active(db, company_id, conversation_id):
    if not conversation_id:
        return False
    return (
        db.query(HumanHandoff)
        .filter(
            HumanHandoff.company_id == company_id,
            HumanHandoff.conversation_id == conversation_id,
            HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES),
        )
        .first()
        is not None
    )


def _conversation(db, channel: AgentChannel, conversation_id: int):
    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.company_id == channel.company_id,
            AIConversation.agent_id == channel.agent_id,
        )
        .first()
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.post("/website/{channel_id}/chat")
def website_chat(
    channel_id: int,
    data: WebsiteChatInput,
    request: Request,
    x_xvond_widget_key: str | None = Header(default=None),
    x_xvond_visitor_token: str | None = Header(default=None),
):
    db = SessionLocal()
    try:
        channel, config = _website_auth(
            db, channel_id, request, x_xvond_widget_key
        )

        if data.conversation_id is not None:
            _require_visitor_token(
                x_xvond_visitor_token,
                channel.id,
                data.conversation_id,
            )

        if data.conversation_id and _human_active(
            db, channel.company_id, data.conversation_id
        ):
            conversation = _conversation(db, channel, data.conversation_id)
            bind_conversation_source(
                db,
                conversation_id=conversation.id,
                company_id=channel.company_id,
                agent_id=channel.agent_id,
                channel_type="website",
                channel_id=channel.id,
            )
            msg = AIMessage(
                conversation_id=conversation.id,
                role="user",
                content=data.message.strip(),
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return {
                "conversation_id": conversation.id,
                "visitor_token": issue_website_visitor_token(
                    channel.id, conversation.id
                ),
                "mode": "human",
                "message": {
                    "id": msg.id,
                    "role": "user",
                    "content": msg.content,
                },
                "response": None,
            }

        agent = agent_runtime.get_agent(
            db, channel.company_id, channel.agent_id
        )
        original_prompt = agent.system_prompt
        try:
            agent.system_prompt = (
                original_prompt + "\n\n" + website_behavior(config)
            ).strip()
            result = agent_runtime.chat(
                db=db,
                company_id=channel.company_id,
                agent_id=channel.agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
            )
            bind_conversation_source(
                db,
                conversation_id=result["conversation_id"],
                company_id=channel.company_id,
                agent_id=channel.agent_id,
                channel_type="website",
                channel_id=channel.id,
            )
            db.commit()
            result["visitor_token"] = issue_website_visitor_token(
                channel.id, result["conversation_id"]
            )
            result["mode"] = (
                "human"
                if _human_active(
                    db, channel.company_id, result["conversation_id"]
                )
                else "ai"
            )
            return result
        finally:
            agent.system_prompt = original_prompt
    finally:
        db.close()


@router.get("/website/{channel_id}/conversation/{conversation_id}/messages")
def website_messages(
    channel_id: int,
    conversation_id: int,
    request: Request,
    after_id: int = 0,
    x_xvond_widget_key: str | None = Header(default=None),
    x_xvond_visitor_token: str | None = Header(default=None),
):
    db = SessionLocal()
    try:
        channel, _config = _website_auth(
            db, channel_id, request, x_xvond_widget_key
        )
        _require_visitor_token(
            x_xvond_visitor_token,
            channel.id,
            conversation_id,
        )
        conversation = _conversation(db, channel, conversation_id)
        items = (
            db.query(AIMessage)
            .filter(
                AIMessage.conversation_id == conversation.id,
                AIMessage.id > max(0, after_id),
            )
            .order_by(AIMessage.id.asc())
            .limit(100)
            .all()
        )
        return {
            "mode": (
                "human"
                if _human_active(db, channel.company_id, conversation.id)
                else "ai"
            ),
            "messages": [
                {"id": x.id, "role": x.role, "content": x.content}
                for x in items
            ],
        }
    finally:
        db.close()


@router.post("/voice/{channel_id}/turn")
def voice_turn(
    channel_id: int,
    data: VoiceTurnInput,
    x_xvond_voice_token: str | None = Header(default=None),
):
    db = SessionLocal()
    try:
        channel = require_channel(db, channel_id, "voice")
        config = reveal_config(channel.config) or {}
        if not secure_equal(x_xvond_voice_token, config.get("auth_token")):
            raise HTTPException(401, "Invalid voice channel token")
        result = agent_runtime.chat(
            db=db,
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            message=data.transcript,
            conversation_id=data.conversation_id,
        )
        bind_conversation_source(
            db,
            conversation_id=result["conversation_id"],
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            channel_type="voice",
            channel_id=channel.id,
            external_contact_id=data.session_id,
        )
        db.commit()
        return {
            "channel_id": channel.id,
            "session_id": data.session_id,
            "conversation_id": result["conversation_id"],
            "text": result["response"]["content"],
        }
    finally:
        db.close()
