from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.admin_channels import _activation_blockers, _ensure_channels_module
from backend.app.core.config_secrets import merge_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.audit.service import audit_service
from backend.app.modules.channels.catalog import validate_channel_config
from backend.app.modules.channels.models import AgentChannel


router = APIRouter(
    prefix="/admin/meta/whatsapp",
    tags=["Xvond Admin - Meta WhatsApp"],
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _meta_settings() -> dict:
    return {
        "app_id": _env("META_APP_ID"),
        "app_secret": _env("META_APP_SECRET"),
        "config_id": _env("META_WHATSAPP_CONFIG_ID"),
        "verify_token": _env("META_WHATSAPP_VERIFY_TOKEN"),
        "graph_api_version": _env("META_GRAPH_API_VERSION", "v23.0"),
        "redirect_uri": _env("META_WHATSAPP_REDIRECT_URI"),
    }


def _ensure_meta_configured() -> dict:
    config = _meta_settings()
    missing = [
        key
        for key in ("app_id", "app_secret", "config_id", "verify_token")
        if not config[key]
    ]
    if missing:
        raise HTTPException(
            status_code=503,
            detail="Meta WhatsApp Embedded Signup is not configured: " + ", ".join(missing),
        )
    return config


def _graph_url(version: str, path: str, params: dict | None = None) -> str:
    base = "https://graph.facebook.com/" + version.strip("/") + "/"
    url = base + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def _graph_request(
    method: str,
    url: str,
    *,
    access_token: str | None = None,
    form: dict | None = None,
) -> dict:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "graph.facebook.com":
        raise HTTPException(status_code=500, detail="Invalid Meta Graph API destination")

    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"Meta Graph API error ({exc.code}): {body_text[:500]}",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Meta Graph API request failed: {str(exc)[:300]}",
        ) from exc


def _exchange_code_for_token(code: str, config: dict) -> str:
    params = {
        "client_id": config["app_id"],
        "client_secret": config["app_secret"],
        "code": code,
    }
    if config["redirect_uri"]:
        params["redirect_uri"] = config["redirect_uri"]
    payload = _graph_request(
        "GET",
        _graph_url(config["graph_api_version"], "oauth/access_token", params),
    )
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=502, detail="Meta did not return an access token")
    return token


def _verify_phone_belongs_to_waba(
    *,
    waba_id: str,
    phone_number_id: str,
    access_token: str,
    graph_api_version: str,
) -> dict:
    payload = _graph_request(
        "GET",
        _graph_url(
            graph_api_version,
            f"{urllib.parse.quote(waba_id, safe='')}/phone_numbers",
            {"fields": "id,display_phone_number,verified_name"},
        ),
        access_token=access_token,
    )
    for item in payload.get("data", []) or []:
        if str(item.get("id") or "") == phone_number_id:
            return item
    raise HTTPException(
        status_code=400,
        detail="The selected phone number does not belong to the selected WhatsApp Business Account",
    )


def _subscribe_app_to_waba(
    *,
    waba_id: str,
    access_token: str,
    graph_api_version: str,
) -> None:
    payload = _graph_request(
        "POST",
        _graph_url(
            graph_api_version,
            f"{urllib.parse.quote(waba_id, safe='')}/subscribed_apps",
        ),
        access_token=access_token,
        form={},
    )
    if payload.get("success") is not True:
        raise HTTPException(
            status_code=502,
            detail="Meta did not confirm WhatsApp webhook subscription",
        )


class EmbeddedSignupComplete(BaseModel):
    agent_id: int
    code: str
    waba_id: str
    phone_number_id: str
    business_id: str | None = None


@router.get("/embedded-signup/config")
def embedded_signup_config(
    agent_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if agent is None:
            raise HTTPException(status_code=404, detail="AI Employee not found")
        config = _meta_settings()
        ready = bool(config["app_id"] and config["config_id"])
        return {
            "ready": ready,
            "agent_id": agent.id,
            "company_id": agent.company_id,
            "app_id": config["app_id"] if ready else None,
            "config_id": config["config_id"] if ready else None,
            "graph_api_version": config["graph_api_version"],
            "feature": "whatsapp_embedded_signup",
            "session_info_version": "3",
        }
    finally:
        db.close()


@router.post("/embedded-signup/complete")
def complete_embedded_signup(
    data: EmbeddedSignupComplete,
    current_admin: User = Depends(require_xvond_admin),
):
    config = _ensure_meta_configured()
    code = data.code.strip()
    waba_id = data.waba_id.strip()
    phone_number_id = data.phone_number_id.strip()
    if not code or not waba_id or not phone_number_id:
        raise HTTPException(400, "code, waba_id and phone_number_id are required")

    access_token = _exchange_code_for_token(code, config)
    phone = _verify_phone_belongs_to_waba(
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        access_token=access_token,
        graph_api_version=config["graph_api_version"],
    )
    _subscribe_app_to_waba(
        waba_id=waba_id,
        access_token=access_token,
        graph_api_version=config["graph_api_version"],
    )

    db = SessionLocal()
    try:
        agent = db.query(AIAgent).filter(AIAgent.id == data.agent_id).first()
        if agent is None:
            raise HTTPException(status_code=404, detail="AI Employee not found")

        channel = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.agent_id == agent.id,
                AgentChannel.channel_type == "whatsapp",
            )
            .first()
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
            "connection_method": "meta_embedded_signup",
            "language": "auto",
            "dialect": "auto",
            "tone": "professional_friendly",
            "response_style": "conversational",
            "response_length": "concise",
            "emoji_style": "minimal",
        }
        merged = merge_config(channel.config if channel else {}, incoming)
        validate_channel_config("whatsapp", merged)

        if channel is None:
            channel = AgentChannel(
                company_id=agent.company_id,
                agent_id=agent.id,
                channel_type="whatsapp",
                config=merged,
                enabled=False,
            )
            db.add(channel)
        else:
            channel.config = merged
            channel.enabled = False
        _ensure_channels_module(db, agent.company_id)
        db.flush()

        blockers = _activation_blockers(db, channel)
        channel.enabled = not blockers
        audit_service.log(
            db=db,
            action="whatsapp.embedded_signup.connected",
            resource_type="agent_channel",
            resource_id=channel.id,
            user_id=current_admin.id,
            company_id=agent.company_id,
            details={
                "agent_id": agent.id,
                "waba_id": waba_id,
                "phone_number_id": phone_number_id,
                "connection_method": "meta_embedded_signup",
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
            "company_id": channel.company_id,
            "agent_id": channel.agent_id,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "display_phone_number": phone.get("display_phone_number"),
            "verified_name": phone.get("verified_name"),
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
