from __future__ import annotations

import hmac
import json
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config_secrets import reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.vapi import normalize_vapi_messages
from backend.app.modules.channels.voice_models import VoiceCallSession
from backend.app.modules.channels.voice_runtime import run_voice_turn


router = APIRouter(
    prefix="/v1/voice",
    tags=["Voice LLM"],
)


class VoiceChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "xvond-agent"
    messages: list[dict] = Field(default_factory=list)
    stream: bool = True
    call_id: str | None = None
    callId: str | None = None
    metadata: dict | None = None


def _bearer_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = value[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token required")
    return token


def _authenticate_channel(channel: AgentChannel, authorization: str | None) -> dict:
    config = reveal_config(channel.config)
    expected = str(config.get("llm_api_key") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Voice channel LLM credential is not configured",
        )

    supplied = _bearer_token(authorization)
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="Invalid voice LLM credential")

    return config


def _resolve_call_id(
    payload: VoiceChatCompletionRequest,
    x_call_id: str | None,
    x_vapi_call_id: str | None,
    x_xvond_call_id: str | None,
) -> str:
    metadata = payload.metadata or {}
    candidates = (
        x_xvond_call_id,
        x_call_id,
        x_vapi_call_id,
        payload.call_id,
        payload.callId,
        metadata.get("call_id"),
        metadata.get("callId"),
        metadata.get("call", {}).get("id")
        if isinstance(metadata.get("call"), dict)
        else None,
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value[:255]

    raise HTTPException(
        status_code=400,
        detail=(
            "Voice call id is required. Configure Vapi to send "
            "X-Xvond-Call-Id: {{call.id}} to the custom LLM."
        ),
    )


def _session_for_call(db, channel: AgentChannel, external_call_id: str) -> VoiceCallSession:
    session = (
        db.query(VoiceCallSession)
        .filter(
            VoiceCallSession.channel_id == channel.id,
            VoiceCallSession.external_call_id == external_call_id,
        )
        .first()
    )
    if session is not None:
        return session

    session = VoiceCallSession(
        company_id=channel.company_id,
        agent_id=channel.agent_id,
        channel_id=channel.id,
        provider="vapi",
        external_call_id=external_call_id,
    )
    db.add(session)
    db.flush()
    return session


def _completion_payload(*, request_id: str, model: str, text: str) -> dict:
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
    }


def _stream_completion(*, request_id: str, model: str, text: str):
    created = int(time.time())
    first = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    yield "data: " + json.dumps(first, ensure_ascii=False) + "\n\n"

    # The Xvond agent/tool loop completes before text is available. We still
    # expose standards-compatible SSE so Vapi can consume the endpoint in
    # streaming mode; provider-level token streaming can be added later.
    chunk_size = 48
    for start in range(0, len(text), chunk_size):
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": text[start : start + chunk_size]},
                    "finish_reason": None,
                }
            ],
        }
        yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"

    final = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield "data: " + json.dumps(final, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


@router.post("/{channel_id}/chat/completions")
def voice_chat_completions(
    channel_id: int,
    payload: VoiceChatCompletionRequest,
    authorization: str | None = Header(default=None),
    x_call_id: str | None = Header(default=None, alias="X-Call-Id"),
    x_vapi_call_id: str | None = Header(default=None, alias="X-Vapi-Call-Id"),
    x_xvond_call_id: str | None = Header(default=None, alias="X-Xvond-Call-Id"),
):
    db = SessionLocal()
    try:
        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.id == channel_id,
                AgentChannel.channel_type == "voice",
                AgentChannel.enabled.is_(True),
            )
            .first()
        )
        if channel is None:
            raise HTTPException(status_code=404, detail="Enabled voice channel not found")

        _authenticate_channel(channel, authorization)
        external_call_id = _resolve_call_id(
            payload,
            x_call_id,
            x_vapi_call_id,
            x_xvond_call_id,
        )

        try:
            _, transcript = normalize_vapi_messages(payload.messages)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        session = _session_for_call(db, channel, external_call_id)

        result = run_voice_turn(
            db=db,
            channel=channel,
            transcript=transcript,
            conversation_id=session.conversation_id,
        )

        if session.conversation_id is None:
            session.conversation_id = int(result["conversation_id"])
        db.commit()

        text = str(result["response"]["content"] or "").strip()
        if not text:
            text = "عذرًا، ما قدرت أجهز الرد الآن."

        request_id = "chatcmpl-" + uuid.uuid4().hex
        model = payload.model or "xvond-agent"

        if payload.stream:
            return StreamingResponse(
                _stream_completion(
                    request_id=request_id,
                    model=model,
                    text=text,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        return _completion_payload(
            request_id=request_id,
            model=model,
            text=text,
        )
    finally:
        db.close()
