from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.core.config_secrets import public_config
from backend.app.core.database.connection import SessionLocal
from backend.app.core.dependencies import require_xvond_admin
from backend.app.models.user import User
from backend.app.modules.audit.models import AuditLog
from backend.app.modules.channels.models import AgentChannel
from backend.app.modules.channels.whatsapp_models import WhatsAppInboundMessage


router = APIRouter(
    prefix="/admin/whatsapp",
    tags=["Xvond Admin - WhatsApp"],
)


@router.get("/companies/{company_id}")
def whatsapp_company_overview(
    company_id: int,
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        channels = (
            db.query(AgentChannel)
            .filter(
                AgentChannel.company_id == company_id,
                AgentChannel.channel_type == "whatsapp",
            )
            .order_by(AgentChannel.id.asc())
            .all()
        )

        return {
            "company_id": company_id,
            "accounts": [
                {
                    "channel_id": channel.id,
                    "agent_id": channel.agent_id,
                    "enabled": channel.enabled,
                    "config": public_config(channel.config),
                    "created_at": channel.created_at,
                }
                for channel in channels
            ],
        }
    finally:
        db.close()


@router.get("/companies/{company_id}/activity")
def whatsapp_company_activity(
    company_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    current_admin: User = Depends(require_xvond_admin),
):
    db = SessionLocal()

    try:
        inbound = (
            db.query(WhatsAppInboundMessage)
            .filter(WhatsAppInboundMessage.company_id == company_id)
            .order_by(WhatsAppInboundMessage.created_at.desc())
            .limit(limit)
            .all()
        )

        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.company_id == company_id,
                AuditLog.action.like("whatsapp.%"),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

        items = []

        for row in inbound:
            items.append(
                {
                    "source": "inbound",
                    "direction": "inbound",
                    "event": "whatsapp.message_received",
                    "message_id": row.external_message_id,
                    "agent_id": row.agent_id,
                    "contact_ref": row.wa_id,
                    "created_at": row.created_at,
                    "details": {},
                }
            )

        for row in audit:
            details = dict(row.details or {})
            action = str(row.action)
            direction = (
                "outbound"
                if action in {
                    "whatsapp.reply_sent",
                    "whatsapp.reply_failed",
                    "whatsapp.reply_retry_scheduled",
                    "whatsapp.handoff_requested",
                }
                else "system"
            )

            items.append(
                {
                    "source": "audit",
                    "direction": direction,
                    "event": action,
                    "message_id": details.get("message_id"),
                    "agent_id": details.get("agent_id"),
                    "contact_ref": details.get("wa_id"),
                    "created_at": row.created_at,
                    "details": details,
                }
            )

        items.sort(
            key=lambda item: item["created_at"],
            reverse=True,
        )

        return {
            "company_id": company_id,
            "count": min(len(items), limit),
            "items": items[:limit],
        }
    finally:
        db.close()
