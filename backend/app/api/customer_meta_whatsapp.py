from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.admin_channels import _activation_blockers, _ensure_channels_module
from backend.app.api.admin_meta_whatsapp import (
    WHATSAPP_BEHAVIOR_DEFAULTS,
    _ensure_meta_configured,
    _exchange_code_for_token,
    _meta_settings,
    _missing_meta_settings,
    _resolve_signup_phone,
    _subscribe_app_to_waba,
)
from backend.app.core.config_secrets import merge_config, reveal_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_customer_manager
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.audit.service import audit_service
from backend.app.modules.channels.catalog import validate_channel_config
from backend.app.modules.channels.models import AgentChannel


router = APIRouter(
    prefix="/customer/meta/whatsapp",
    tags=["Customer - Meta WhatsApp"],
)

_META_CONNECTION_METHODS = {
    "meta_embedded_signup",
    "meta_embedded_signup_coexistence",
}


class CustomerEmbeddedSignupComplete(BaseModel):
    agent_id: int
    code: str
    waba_id: str
    phone_number_id: str | None = None
    business_id: str | None = None
    connection_mode: str | None = None


def _customer_agent(db, current_user: User, agent_id: int) -> AIAgent:
    agent = (
        db.query(AIAgent)
        .filter(
            AIAgent.id == agent_id,
            AIAgent.company_id == current_user.company_id,
        )
        .first()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="AI Employee not found")
    return agent


def _meta_channel_connected(channel: AgentChannel | None, channel_config: dict) -> bool:
    if channel is None:
        return False
    method = str(channel_config.get("connection_method") or "").strip()
    if method not in _META_CONNECTION_METHODS:
        return False
    required = (
        channel_config.get("waba_id"),
        channel_config.get("phone_number_id"),
        channel_config.get("access_token"),
    )
    return all(str(value or "").strip() for value in required)


@router.get("/embedded-signup/config")
def embedded_signup_config(
    agent_id: int,
    current_user: User = Depends(require_customer_manager),
):
    db = SessionLocal()
    try:
        agent = _customer_agent(db, current_user, agent_id)
        meta = _meta_settings()
        missing = _missing_meta_settings(meta)
        ready = not missing
        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id == current_user.company_id,
                AgentChannel.agent_id == agent.id,
                AgentChannel.channel_type == "whatsapp",
            )
            .first()
        )
        channel_config = reveal_config(channel.config) if channel is not None else {}
        connected = _meta_channel_connected(channel, channel_config)
        blockers = _activation_blockers(db, channel) if channel is not None else []
        enabled = bool(channel.enabled) if channel is not None else False
        return {
            "ready": ready,
            "agent_id": agent.id,
            "company_id": agent.company_id,
            "app_id": meta["app_id"] if ready else None,
            "config_id": meta["config_id"] if ready else None,
            "graph_api_version": meta["graph_api_version"],
            "feature_type": meta.get("feature_type") or None,
            "session_info_version": meta.get("session_info_version") or None,
            "missing_settings": missing,
            "channel_id": channel.id if channel is not None else None,
            "connected": connected,
            "enabled": enabled,
            "runtime_ready": bool(connected and enabled and not blockers),
            "blockers": blockers,
            "connection_method": channel_config.get("connection_method"),
            "coexistence": bool(channel_config.get("coexistence")),
            "display_phone_number": channel_config.get("display_phone_number"),
            "verified_name": channel_config.get("verified_name"),
        }
    finally:
        db.close()


@router.post("/embedded-signup/complete")
def complete_embedded_signup(
    data: CustomerEmbeddedSignupComplete,
    current_user: User = Depends(require_customer_manager),
):
    config = _ensure_meta_configured()
    code = data.code.strip()
    waba_id = data.waba_id.strip()
    requested_phone_number_id = str(data.phone_number_id or "").strip() or None
    connection_mode = str(data.connection_mode or "embedded_signup").strip()
    if connection_mode not in {"embedded_signup", "coexistence"}:
        raise HTTPException(status_code=400, detail="Invalid WhatsApp connection mode")
    if not code or not waba_id:
        raise HTTPException(status_code=400, detail="code and waba_id are required")

    # Validate tenant ownership before exchanging any Meta authorization code.
    db = SessionLocal()
    try:
        agent = _customer_agent(db, current_user, data.agent_id)
        agent_id = agent.id
        company_id = agent.company_id
    finally:
        db.close()

    access_token = _exchange_code_for_token(code, config)
    phone = _resolve_signup_phone(
        waba_id=waba_id,
        phone_number_id=requested_phone_number_id,
        access_token=access_token,
        graph_api_version=config["graph_api_version"],
    )
    phone_number_id = str(phone.get("id") or "").strip()
    if not phone_number_id:
        raise HTTPException(status_code=502, detail="Meta did not return a usable phone number ID")

    _subscribe_app_to_waba(
        waba_id=waba_id,
        access_token=access_token,
        graph_api_version=config["graph_api_version"],
    )

    db = SessionLocal()
    try:
        # Re-check ownership in case the account changed while Meta signup was open.
        agent = _customer_agent(db, current_user, agent_id)
        if agent.company_id != company_id:
            raise HTTPException(status_code=409, detail="AI Employee company changed during WhatsApp setup")

        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id == company_id,
                AgentChannel.agent_id == agent.id,
                AgentChannel.channel_type == "whatsapp",
            )
            .first()
        )
        method = (
            "meta_embedded_signup_coexistence"
            if connection_mode == "coexistence"
            else "meta_embedded_signup"
        )
        incoming = {
            "waba_id": waba_id,
            "meta_business_id": data.business_id,
            "phone_number_id": phone_number_id,
            "display_phone_number": phone.get("display_phone_number"),
            "verified_name": phone.get("verified_name"),
            "access_token": access_token,
            "verify_token": config["verify_token"],
            "app_secret": config["app_secret"],
            "graph_api_version": config["graph_api_version"],
            "connection_method": method,
            "coexistence": connection_mode == "coexistence",
        }
        if channel is None:
            incoming.update(WHATSAPP_BEHAVIOR_DEFAULTS)

        merged = merge_config(channel.config if channel else {}, incoming)
        validate_channel_config("whatsapp", reveal_config(merged))

        if channel is None:
            channel = AgentChannel(
                company_id=company_id,
                agent_id=agent.id,
                channel_type="whatsapp",
                config=merged,
                enabled=False,
            )
            db.add(channel)
        else:
            channel.config = merged
            channel.enabled = False

        _ensure_channels_module(db, company_id)
        db.flush()
        blockers = _activation_blockers(db, channel)
        channel.enabled = not blockers

        audit_service.log(
            db=db,
            action="whatsapp.customer_embedded_signup.connected",
            resource_type="agent_channel",
            resource_id=channel.id,
            user_id=current_user.id,
            company_id=company_id,
            details={
                "agent_id": agent.id,
                "waba_id": waba_id,
                "phone_number_id": phone_number_id,
                "connection_method": method,
                "coexistence": connection_mode == "coexistence",
                "webhook_subscribed": True,
                "runtime_ready": not blockers,
                "blockers": blockers,
            },
        )
        db.commit()
        db.refresh(channel)
        return {
            "status": "connected" if not blockers else "connected_needs_setup",
            "channel_id": channel.id,
            "company_id": company_id,
            "agent_id": agent.id,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "display_phone_number": phone.get("display_phone_number"),
            "verified_name": phone.get("verified_name"),
            "connection_mode": connection_mode,
            "coexistence": connection_mode == "coexistence",
            "enabled": bool(channel.enabled),
            "runtime_ready": bool(channel.enabled and not blockers),
            "ready": not blockers,
            "blockers": blockers,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
