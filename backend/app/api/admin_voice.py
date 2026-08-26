from __future__ import annotations

import os
import secrets
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.config_secrets import merge_config, reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.audit.service import audit_service
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.vapi import build_vapi_assistant_payload
from backend.app.modules.channels.vapi_api import (
    attach_assistant_to_phone,
    create_assistant,
    create_custom_llm_credential,
    get_phone_number,
    list_phone_numbers,
    update_assistant,
)


router = APIRouter(
    prefix="/admin/voice",
    tags=["Xvond Admin - Voice"],
)


class VapiProvisionRequest(BaseModel):
    phone_number_id: str


def _public_base_url() -> str:
    value = str(os.getenv("XVOND_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not value:
        raise HTTPException(
            status_code=503,
            detail="XVOND_PUBLIC_BASE_URL is not configured on the Xvond server",
        )
    if not value.lower().startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="XVOND_PUBLIC_BASE_URL must use HTTPS for production voice calls",
        )
    return value


def _assistant_name(agent: AIAgent) -> str:
    name = str(getattr(agent, "name", "") or "Xvond Voice Agent").strip()
    return name[:40] or "Xvond Voice Agent"


@router.get("/vapi/phone-numbers")
def vapi_phone_numbers(
    current_admin: User = Depends(require_xvond_admin),
):
    items = list_phone_numbers()
    return {
        "phone_numbers": [
            {
                "id": str(item.get("id") or ""),
                "number": str(item.get("number") or item.get("phoneNumber") or ""),
                "name": str(item.get("name") or item.get("number") or ""),
                "provider": item.get("provider"),
                "assistant_id": item.get("assistantId"),
            }
            for item in items
            if item.get("id")
        ]
    }


@router.get("/channels/{channel_id}/vapi/status")
def vapi_channel_status(
    channel_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.id == channel_id,
                AgentChannel.channel_type == "voice",
            )
            .first()
        )
        if channel is None:
            raise HTTPException(status_code=404, detail="Voice channel not found")

        config = reveal_config(channel.config)
        return {
            "channel_id": channel.id,
            "company_id": channel.company_id,
            "agent_id": channel.agent_id,
            "enabled": channel.enabled,
            "provider": config.get("provider"),
            "phone_number": config.get("phone_number"),
            "vapi_assistant_id": config.get("vapi_assistant_id"),
            "vapi_phone_number_id": config.get("vapi_phone_number_id"),
            "llm_credential_ready": bool(config.get("llm_api_key")),
            "vapi_credential_ready": bool(config.get("vapi_llm_credential_id")),
            "provisioned": bool(
                config.get("vapi_assistant_id")
                and config.get("vapi_llm_credential_id")
                and config.get("vapi_phone_number_id")
                and config.get("phone_number")
            ),
        }
    finally:
        db.close()


@router.post("/channels/{channel_id}/vapi/provision")
def provision_vapi_voice_channel(
    channel_id: int,
    data: VapiProvisionRequest,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.id == channel_id,
                AgentChannel.channel_type == "voice",
            )
            .first()
        )
        if channel is None:
            raise HTTPException(status_code=404, detail="Voice channel not found")

        agent = (
            db.query(AIAgent)
            .filter(
                AIAgent.id == channel.agent_id,
                AIAgent.company_id == channel.company_id,
            )
            .first()
        )
        if agent is None:
            raise HTTPException(status_code=404, detail="AI Agent not found")

        phone_number_id = str(data.phone_number_id or "").strip()
        if not phone_number_id:
            raise HTTPException(
                status_code=400,
                detail="A real Vapi phone_number_id is required",
            )

        # Validate the Vapi number before creating or changing local state.
        phone = get_phone_number(phone_number_id)
        phone_number = str(phone.get("number") or "").strip()
        if not phone_number:
            raise HTTPException(
                status_code=502,
                detail="Vapi phone number resource did not contain a phone number",
            )

        config = reveal_config(channel.config)
        llm_api_key = str(config.get("llm_api_key") or "").strip()
        if not llm_api_key:
            llm_api_key = secrets.token_urlsafe(48)

        credential_id = str(config.get("vapi_llm_credential_id") or "").strip()
        if not credential_id:
            credential = create_custom_llm_credential(llm_api_key)
            credential_id = str(credential.get("id") or "").strip()
            if not credential_id:
                raise HTTPException(
                    status_code=502,
                    detail="Vapi did not return a custom LLM credential id",
                )

        base_url = _public_base_url()
        model_url = urljoin(
            base_url + "/",
            f"v1/voice/{channel.id}/chat/completions",
        )

        assistant_payload = build_vapi_assistant_payload(
            assistant_name=_assistant_name(agent),
            model_url=model_url,
            channel_config=config,
            credential_id=credential_id,
        )

        assistant_id = str(config.get("vapi_assistant_id") or "").strip()
        if assistant_id:
            update_assistant(assistant_id, assistant_payload)
        else:
            assistant = create_assistant(assistant_payload)
            assistant_id = str(assistant.get("id") or "").strip()
            if not assistant_id:
                raise HTTPException(
                    status_code=502,
                    detail="Vapi did not return an assistant id",
                )

        phone_result = attach_assistant_to_phone(
            phone_number_id,
            assistant_id,
        )
        bound_assistant_id = str(
            phone_result.get("assistantId") or assistant_id
        ).strip()
        if bound_assistant_id != assistant_id:
            raise HTTPException(
                status_code=502,
                detail="Vapi phone number was not bound to the expected assistant",
            )

        incoming = {
            "provider": "vapi",
            "llm_api_key": llm_api_key,
            "vapi_llm_credential_id": credential_id,
            "vapi_assistant_id": assistant_id,
            "vapi_phone_number_id": phone_number_id,
            "phone_number": phone_number,
            "vapi_model_url": model_url,
            "provisioning_method": "xvond_vapi_api",
        }
        channel.config = merge_config(channel.config, incoming)
        channel.enabled = True

        audit_service.log(
            db=db,
            company_id=channel.company_id,
            action="voice.vapi.provisioned",
            resource_type="channel",
            resource_id=channel.id,
            user_id=current_admin.id,
            details={
                "agent_id": channel.agent_id,
                "vapi_assistant_id": assistant_id,
                "vapi_phone_number_id": phone_number_id,
                "phone_number": phone_number,
                "phone_bound": True,
            },
        )

        db.commit()
        db.refresh(channel)

        return {
            "status": "connected",
            "channel_id": channel.id,
            "company_id": channel.company_id,
            "agent_id": channel.agent_id,
            "vapi_assistant_id": assistant_id,
            "vapi_phone_number_id": phone_number_id,
            "phone_number": phone_number,
            "model_url": model_url,
            "phone_bound": True,
        }
    finally:
        db.close()
