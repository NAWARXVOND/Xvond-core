from __future__ import annotations

import hmac
import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.config_secrets import reveal_config
from backend.app.core.customer_runtime_policy import is_service_access_error, safe_service_unavailable_message
from backend.app.core.database.connection import SessionLocal
from backend.app.modules.ai_agent.models import AIConversation, AIMessage
from backend.app.modules.channels.conversation_source import bind_conversation_source
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.vapi import build_voice_behavior_prompt, normalize_vapi_messages
from backend.app.modules.tools.business_models import HumanHandoff


router = APIRouter(prefix="/v1/voice", tags=["Voice LLM"])


class VoiceChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "xvond-agent"
    messages: list[dict] = Field(default_factory=list)
    stream: bool = True
    call_id: str | None = None
    callId: str | None = None
    metadata: dict | None = None


def _bearer_secret(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        return ""
    return value[7:].strip()


def _call_id(data: VoiceChatCompletionRequest, headers: list[str | None]) -> str:
    for value in headers:
        if str(value or "").strip():
            return str(value).strip()[:200]
    for value in (data.call_id, data.callId):
        if str(value or "").strip():
            return str(value).strip()[:200]
    metadata = data.metadata or {}
    for key in ("call_id", "callId"):
        value = metadata.get(key)
        if str(value or "").strip():
            return str(value).strip()[:200]
    call = metadata.get("call")
    if isinstance(call, dict) and str(call.get("id") or "").strip():
        return str(call.get("id")).strip()[:200]
    raise HTTPException(status_code=400, detail="Voice call id is required")


def _existing_conversation(db, channel: AgentChannel, external_call_id: str) -> int | None:
    row = (
        db.query(AIConversation)
        .filter(
            AIConversation.company_id == channel.company_id,
            AIConversation.agent_id == channel.agent_id,
            AIConversation.channel_type == "voice",
            AIConversation.channel_id == channel.id,
            AIConversation.external_contact_id == external_call_id,
        )
        .order_by(AIConversation.id.desc())
        .first()
    )
    return row.id if row else None


def _completion_payload(conversation_id: int, text: str, model: str) -> dict:
    return {
        "id": f"chatcmpl-xvond-{conversation_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or "xvond-agent",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


def _sse_chunks(conversation_id: int, text: str, model: str) -> Iterator[str]:
    created = int(time.time())
    completion_id = f"chatcmpl-xvond-{conversation_id}"
    first = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model or "xvond-agent",
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield "data: " + json.dumps(first) + "\n\n"
    for start in range(0, len(text), 48):
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model or "xvond-agent",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": text[start : start + 48]},
                    "finish_reason": None,
                }
            ],
        }
        yield "data: " + json.dumps(chunk) + "\n\n"
    done = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model or "xvond-agent",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield "data: " + json.dumps(done) + "\n\n"
    yield "data: [DONE]\n\n"


def _voice_service_fallback(db, channel: AgentChannel, transcript: str, conversation_id: int | None, external_call_id: str):
    db.rollback()
    conversation = agent_runtime.get_or_create_conversation(
        db=db,
        company_id=channel.company_id,
        agent_id=channel.agent_id,
        conversation_id=conversation_id,
        message=transcript,
    )
    bind_conversation_source(
        db,
        conversation_id=conversation.id,
        company_id=channel.company_id,
        agent_id=channel.agent_id,
        channel_type="voice",
        channel_id=channel.id,
        external_contact_id=external_call_id,
    )
    agent = agent_runtime.get_agent(db, channel.company_id, channel.agent_id)
    safe_text = safe_service_unavailable_message(agent.system_prompt or "", transcript)
    db.add(AIMessage(conversation_id=conversation.id, role="user", content=transcript))
    db.add(AIMessage(conversation_id=conversation.id, role="assistant", content=safe_text))
    existing_handoff = (
        db.query(HumanHandoff)
        .filter(
            HumanHandoff.company_id == channel.company_id,
            HumanHandoff.conversation_id == conversation.id,
            HumanHandoff.status.in_(["pending", "in_progress"]),
        )
        .first()
    )
    if existing_handoff is None:
        db.add(
            HumanHandoff(
                company_id=channel.company_id,
                agent_id=channel.agent_id,
                conversation_id=conversation.id,
                reason="service_limit_or_entitlement",
                priority="high",
                department="customer_service",
                status="pending",
            )
        )
    db.commit()
    return {"conversation_id": conversation.id, "response": {"content": safe_text}}


@router.post("/{channel_id}/chat/completions")
def voice_chat_completions(
    channel_id: int,
    data: VoiceChatCompletionRequest,
    authorization: str | None = Header(default=None),
    x_xvond_call_id: str | None = Header(default=None),
    x_call_id: str | None = Header(default=None),
    x_vapi_call_id: str | None = Header(default=None),
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
            raise HTTPException(status_code=404, detail="Voice channel unavailable")

        config = reveal_config(channel.config) or {}
        expected = str(config.get("llm_api_key") or "").strip()
        if not expected:
            raise HTTPException(status_code=503, detail="Voice LLM credential is not configured")
        received = _bearer_secret(authorization)
        if not received or not hmac.compare_digest(received, expected):
            raise HTTPException(status_code=401, detail="Invalid voice LLM credential")

        external_call_id = _call_id(
            data,
            [x_xvond_call_id, x_call_id, x_vapi_call_id],
        )
        try:
            _prior, transcript = normalize_vapi_messages(data.messages)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        conversation_id = _existing_conversation(db, channel, external_call_id)
        agent = agent_runtime.get_agent(db, channel.company_id, channel.agent_id)
        original_prompt = agent.system_prompt or ""
        try:
            agent.system_prompt = (
                original_prompt + "\n\n" + build_voice_behavior_prompt(config)
            ).strip()
            try:
                result = agent_runtime.chat(
                    db=db,
                    company_id=channel.company_id,
                    agent_id=channel.agent_id,
                    message=transcript,
                    conversation_id=conversation_id,
                    commit=False,
                )
            except HTTPException as exc:
                if not is_service_access_error(exc):
                    raise
                result = _voice_service_fallback(
                    db,
                    channel,
                    transcript,
                    conversation_id,
                    external_call_id,
                )
        finally:
            agent.system_prompt = original_prompt

        bind_conversation_source(
            db,
            conversation_id=result["conversation_id"],
            company_id=channel.company_id,
            agent_id=channel.agent_id,
            channel_type="voice",
            channel_id=channel.id,
            external_contact_id=external_call_id,
        )
        db.commit()

        text = str(result.get("response", {}).get("content") or "")
        if data.stream:
            return StreamingResponse(
                _sse_chunks(result["conversation_id"], text, data.model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )
        return _completion_payload(result["conversation_id"], text, data.model)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
