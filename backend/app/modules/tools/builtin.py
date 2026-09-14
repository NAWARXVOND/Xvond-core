from datetime import date, time

from backend.app.core.error_safety import safe_error_label
from backend.app.core.http_security import safe_http_request, validate_public_http_url
from backend.app.modules.ai_agent.models import AIConversation
from backend.app.modules.channels.handoff import activate_human_handoff
from backend.app.modules.channels.whatsapp_models import WhatsAppSession
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service
from backend.app.modules.tools.base import AgentTool, ToolResult
from backend.app.modules.tools.business_models import (
    ActionRequest,
    Booking,
    HumanHandoff,
    Lead,
)


LIVE_HUMAN_HANDOFF_CHANNELS = {"whatsapp", "website"}
ACTIVE_HANDOFF_STATUSES = {"pending", "in_progress"}


def _fact_tokens(value: str) -> set[str]:
    tokens = set()
    for token in knowledge_service.normalize(value or "").split():
        if token.startswith("ال") and len(token) > 4:
            token = token[2:]
        if len(token) >= 2:
            tokens.add(token)
    return tokens


def _known_business_item(db, company_id: int, agent_id: int, value: str) -> bool:
    target = _fact_tokens(value)
    if not target:
        return False
    rows = (
        db.query(KnowledgeDocument)
        .join(AgentKnowledge, AgentKnowledge.document_id == KnowledgeDocument.id)
        .filter(
            KnowledgeDocument.company_id == company_id,
            KnowledgeDocument.enabled.is_(True),
            AgentKnowledge.agent_id == agent_id,
            AgentKnowledge.enabled.is_(True),
        )
        .all()
    )
    for doc in rows:
        content_tokens = _fact_tokens(doc.content or "")
        matched = len(target & content_tokens)
        if matched == len(target) or (
            len(target) >= 2 and matched / len(target) >= 0.75
        ):
            return True
    return False


def _valid_iso_date(value):
    try:
        date.fromisoformat(str(value))
        return True
    except Exception:
        return False


def _valid_iso_time(value):
    try:
        time.fromisoformat(str(value))
        return True
    except Exception:
        return False


def _safe_external_result(result: dict, config: dict) -> dict:
    """Expose only transport metadata by default.

    Arbitrary provider bodies can contain credentials, PII, or large internal
    payloads. They are available to the AI only when an operator explicitly opts
    in for that integration, and even then are tightly bounded.
    """
    payload = {
        "status_code": int(result.get("status_code") or 0),
        "truncated": bool(result.get("truncated")),
    }
    location = str(result.get("redirect_location") or "").strip()
    if location:
        payload["redirected"] = True
    if bool((config or {}).get("expose_response_to_ai", False)):
        payload["response"] = str(result.get("response") or "")[:12000]
    return payload


class LeadTool(AgentTool):
    name = "lead"
    description = "Capture and save a customer lead when the customer has actually expressed interest."
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "interest": {"type": "string"},
            "notes": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        db = context["db"]
        lead = Lead(
            company_id=context["company_id"],
            agent_id=context["agent_id"],
            name=arguments.get("name"),
            phone=arguments.get("phone"),
            email=arguments.get("email"),
            interest=arguments.get("interest"),
            notes=arguments.get("notes"),
        )
        db.add(lead)
        db.flush()
        return ToolResult(
            success=True,
            data={"action": "lead_created", "lead_id": lead.id, "status": lead.status},
        )


class BookingTool(AgentTool):
    name = "booking"
    description = "Check availability and create, reschedule or cancel a real booking in Xvond's internal booking store. Use only services present in company knowledge. Never confirm unless this tool returns success."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["check_availability", "create", "reschedule", "cancel"],
            },
            "booking_id": {"type": "integer"},
            "customer_name": {"type": "string"},
            "phone": {"type": "string"},
            "service": {"type": "string"},
            "date": {"type": "string"},
            "time": {"type": "string"},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        db = context["db"]
        action = arguments.get("action")
        cid = context["company_id"]
        aid = context["agent_id"]
        if action in ("check_availability", "create"):
            missing = [
                x
                for x in ("service", "date", "time")
                if not str(arguments.get(x) or "").strip()
            ]
            if missing:
                return ToolResult(
                    success=False,
                    error="Missing required booking fields: " + ", ".join(missing),
                )
            service = str(arguments["service"]).strip()
            booking_date = str(arguments["date"]).strip()
            booking_time = str(arguments["time"]).strip()
            if not _valid_iso_date(booking_date):
                return ToolResult(success=False, error="Booking date must use YYYY-MM-DD")
            if not _valid_iso_time(booking_time):
                return ToolResult(success=False, error="Booking time must use HH:MM")
            if not _known_business_item(db, cid, aid, service):
                return ToolResult(
                    success=False,
                    error="Requested service is not present in company knowledge",
                )
            conflict = (
                db.query(Booking)
                .filter(
                    Booking.company_id == cid,
                    Booking.booking_date == booking_date,
                    Booking.booking_time == booking_time,
                    Booking.status.in_(["pending", "confirmed"]),
                )
                .first()
            )
            if action == "check_availability":
                return ToolResult(
                    success=True,
                    data={
                        "action": "availability_checked",
                        "available": conflict is None,
                        "date": booking_date,
                        "time": booking_time,
                        "service": service,
                    },
                )
            missing_customer = [
                x
                for x in ("customer_name", "phone")
                if not str(arguments.get(x) or "").strip()
            ]
            if missing_customer:
                return ToolResult(
                    success=False,
                    error="Missing customer fields: " + ", ".join(missing_customer),
                )
            if conflict:
                return ToolResult(
                    success=False,
                    error="Requested booking time is not available",
                    data={
                        "available": False,
                        "date": booking_date,
                        "time": booking_time,
                    },
                )
            booking = Booking(
                company_id=cid,
                agent_id=aid,
                customer_name=str(arguments["customer_name"]).strip(),
                phone=str(arguments["phone"]).strip(),
                service=service,
                booking_date=booking_date,
                booking_time=booking_time,
                status="confirmed",
            )
            db.add(booking)
            db.flush()
            return ToolResult(
                success=True,
                data={
                    "action": "booking_created",
                    "booking_id": booking.id,
                    "status": "confirmed",
                },
            )

        booking_id = arguments.get("booking_id")
        if not booking_id:
            return ToolResult(success=False, error="booking_id is required")
        booking = (
            db.query(Booking)
            .filter(
                Booking.id == booking_id,
                Booking.company_id == cid,
                Booking.agent_id == aid,
            )
            .first()
        )
        if not booking:
            return ToolResult(success=False, error="Booking not found")
        if action == "cancel":
            booking.status = "cancelled"
            db.flush()
            return ToolResult(
                success=True,
                data={"action": "booking_cancelled", "booking_id": booking.id},
            )
        if action == "reschedule":
            new_date = str(arguments.get("date") or booking.booking_date).strip()
            new_time = str(arguments.get("time") or booking.booking_time).strip()
            if not _valid_iso_date(new_date) or not _valid_iso_time(new_time):
                return ToolResult(
                    success=False,
                    error="Reschedule date/time must use YYYY-MM-DD and HH:MM",
                )
            booking.booking_date = new_date
            booking.booking_time = new_time
            booking.status = "confirmed"
            db.flush()
            return ToolResult(
                success=True,
                data={
                    "action": "booking_rescheduled",
                    "booking_id": booking.id,
                    "date": new_date,
                    "time": new_time,
                },
            )
        return ToolResult(success=False, error="Invalid booking action")


class OrderTool(AgentTool):
    name = "order"
    description = "Create a real internal customer order/request in Xvond after collecting every configured required detail and obtaining customer confirmation. The order is saved for the business team; do not hand off merely because an order was submitted."
    input_schema = {
        "type": "object",
        "properties": {
            "details": {"type": "object", "additionalProperties": True},
            "summary": {"type": "string"},
        },
        "required": ["details", "summary"],
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        config = context.get("config", {}) or {}
        required = [
            str(x).strip()
            for x in (config.get("required_fields") or [])
            if str(x).strip()
        ]
        details = arguments.get("details") or {}
        if not isinstance(details, dict):
            return ToolResult(success=False, error="Order details must be structured")
        missing = [
            field for field in required if not str(details.get(field) or "").strip()
        ]
        if missing:
            return ToolResult(
                success=False,
                error="Missing required order details: " + ", ".join(missing),
            )
        summary = str(arguments.get("summary") or "").strip()
        if not summary:
            return ToolResult(success=False, error="Order summary is required")
        db = context["db"]
        request = ActionRequest(
            company_id=context["company_id"],
            agent_id=context["agent_id"],
            conversation_id=context.get("conversation_id"),
            action_type="order",
            details=details,
            summary=summary,
            status="new",
        )
        db.add(request)
        db.flush()
        return ToolResult(
            success=True,
            data={
                "action": "order_created",
                "order_id": request.id,
                "request_id": request.id,
                "status": "new",
                "details": details,
            },
        )


class HumanHandoffTool(AgentTool):
    name = "human_handoff"
    description = "Escalate a live text conversation to a human employee when the customer explicitly requests a human or configured policy requires escalation. Use only when Xvond has a real same-channel handoff path; never claim a transfer on unsupported channels."
    input_schema = {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
            "department": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        db = context["db"]
        conversation_id = context.get("conversation_id")
        cid = context["company_id"]
        aid = context["agent_id"]
        if conversation_id is None:
            return ToolResult(success=False, error="Human handoff requires a live customer conversation")
        conversation = (
            db.query(AIConversation)
            .filter(
                AIConversation.id == conversation_id,
                AIConversation.company_id == cid,
                AIConversation.agent_id == aid,
            )
            .first()
        )
        if conversation is None:
            return ToolResult(success=False, error="Conversation not found for human handoff")
        channel_type = str(conversation.channel_type or "").strip().lower()
        if channel_type not in LIVE_HUMAN_HANDOFF_CHANNELS:
            return ToolResult(
                success=False,
                error=f"Live human handoff is not available on {channel_type or 'this'} channel yet",
                data={"action": "human_handoff_unavailable", "channel_type": channel_type or None},
            )
        session = None
        if channel_type == "whatsapp":
            session = (
                db.query(WhatsAppSession)
                .filter(
                    WhatsAppSession.company_id == cid,
                    WhatsAppSession.agent_id == aid,
                    WhatsAppSession.conversation_id == conversation_id,
                )
                .first()
            )
            if session is None:
                return ToolResult(success=False, error="WhatsApp session is unavailable for live human handoff")
        reason = arguments.get("reason") or "ai_handoff"
        priority = arguments.get("priority", "normal")
        department = arguments.get(
            "department",
            context.get("config", {}).get("department", "customer_service"),
        )
        handoff = (
            db.query(HumanHandoff)
            .filter(
                HumanHandoff.company_id == cid,
                HumanHandoff.conversation_id == conversation_id,
                HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES),
            )
            .order_by(HumanHandoff.id.desc())
            .first()
        )
        if handoff is None:
            handoff = HumanHandoff(
                company_id=cid,
                agent_id=aid,
                conversation_id=conversation_id,
                reason=reason,
                priority=priority,
                department=department,
                status="pending",
            )
            db.add(handoff)
            db.flush()
        else:
            handoff.reason = handoff.reason or reason
            handoff.priority = priority
            handoff.department = department
        if session is not None:
            activate_human_handoff(session, reason=reason)
        db.flush()
        return ToolResult(
            success=True,
            data={
                "action": "human_handoff_created",
                "handoff_id": handoff.id,
                "status": handoff.status,
                "ai_paused": True,
                "claim_required": handoff.assigned_user_id is None,
                "channel_type": channel_type,
            },
        )


class WebhookTool(AgentTool):
    name = "webhook"
    description = "Send data to an external webhook."
    input_schema = {
        "type": "object",
        "properties": {"payload": {"type": "object"}},
        "additionalProperties": True,
    }

    def execute(self, arguments, context):
        config = context.get("config", {}) or {}
        url = config.get("url")
        if not url:
            return ToolResult(success=False, error="Webhook URL is not configured")
        try:
            validate_public_http_url(url)
            result = safe_http_request(
                url=url,
                method=config.get("method", "POST"),
                headers={
                    "Content-Type": "application/json",
                    **(config.get("headers", {}) or {}),
                },
                json_data=arguments.get("payload", arguments),
                timeout=config.get("timeout", 15),
            )
            status = int(result["status_code"])
            return ToolResult(
                success=200 <= status < 300,
                data=_safe_external_result(result, config),
                error=None if 200 <= status < 300 else f"Webhook returned HTTP {status}",
            )
        except Exception as exc:
            return ToolResult(success=False, error=safe_error_label(exc))


class CustomAPITool(AgentTool):
    name = "custom_api"
    description = "Call a configured external business API."
    input_schema = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
            "payload": {},
        },
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        config = context.get("config", {}) or {}
        base_url = config.get("base_url")
        if not base_url:
            return ToolResult(success=False, error="API base_url is not configured")
        endpoint = str(arguments.get("endpoint", "") or "").strip()
        if endpoint.lower().startswith(("http://", "https://")) or endpoint.startswith("//"):
            return ToolResult(success=False, error="API endpoint must be a relative path")
        url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
        try:
            validate_public_http_url(base_url)
            validate_public_http_url(url)
            headers = {
                "Content-Type": "application/json",
                **(config.get("headers", {}) or {}),
            }
            api_key = config.get("api_key")
            if api_key and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {api_key}"
            result = safe_http_request(
                url=url,
                method=arguments.get("method", "POST"),
                headers=headers,
                json_data=arguments.get("payload"),
                timeout=config.get("timeout", 15),
            )
            status = int(result["status_code"])
            return ToolResult(
                success=200 <= status < 300,
                data=_safe_external_result(result, config),
                error=None if 200 <= status < 300 else f"External API returned HTTP {status}",
            )
        except Exception as exc:
            return ToolResult(success=False, error=safe_error_label(exc))


BUILTIN_TOOLS = [
    LeadTool(),
    BookingTool(),
    OrderTool(),
    HumanHandoffTool(),
    WebhookTool(),
    CustomAPITool(),
]
