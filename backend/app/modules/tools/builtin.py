from datetime import date, time

from backend.app.core.http_security import safe_http_request, validate_public_http_url
from backend.app.modules.tools.base import AgentTool, ToolResult
from backend.app.modules.tools.business_models import Lead, Booking, Order, HumanHandoff
from backend.app.modules.channels.whatsapp_models import WhatsAppSession
from backend.app.modules.channels.handoff import activate_human_handoff
from backend.app.modules.knowledge.models import AgentKnowledge, KnowledgeDocument
from backend.app.modules.knowledge.service import knowledge_service


def _fact_tokens(value: str) -> set[str]:
    tokens = set()
    for token in knowledge_service.normalize(value or "").split():
        if token.startswith("ال") and len(token) > 4:
            token = token[2:]
        if len(token) >= 2:
            tokens.add(token)
    return tokens


def _known_business_item(db, company_id: int, agent_id: int, value: str) -> bool:
    """Require action targets to exist in the employee's enabled business knowledge.

    This is a hard guardrail below the LLM: a hallucinated service/product cannot be
    booked or ordered merely because the model emitted a tool call.
    """
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
        if matched == len(target) or (len(target) >= 2 and matched / len(target) >= 0.75):
            return True
    return False


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(str(value))
        return True
    except Exception:
        return False


def _valid_iso_time(value: str) -> bool:
    try:
        time.fromisoformat(str(value))
        return True
    except Exception:
        return False


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
        return ToolResult(success=True, data={"action": "lead_created", "lead_id": lead.id, "status": lead.status})


class BookingTool(AgentTool):
    name = "booking"
    description = "Check availability and create, reschedule or cancel a real booking in Xvond's internal booking store. Use only services present in company knowledge. Never confirm unless this tool returns success."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["check_availability", "create", "reschedule", "cancel"]},
            "booking_id": {"type": "integer"},
            "customer_name": {"type": "string"},
            "phone": {"type": "string"},
            "service": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM in the business local time"},
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
            missing = [x for x in ("service", "date", "time") if not str(arguments.get(x) or "").strip()]
            if missing:
                return ToolResult(success=False, error="Missing required booking fields: " + ", ".join(missing))
            service = str(arguments["service"]).strip()
            booking_date = str(arguments["date"]).strip()
            booking_time = str(arguments["time"]).strip()
            if not _valid_iso_date(booking_date):
                return ToolResult(success=False, error="Booking date must use YYYY-MM-DD")
            if not _valid_iso_time(booking_time):
                return ToolResult(success=False, error="Booking time must use HH:MM")
            if not _known_business_item(db, cid, aid, service):
                return ToolResult(success=False, error="Requested service is not present in company knowledge")
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
                return ToolResult(success=True, data={"action": "availability_checked", "available": conflict is None, "date": booking_date, "time": booking_time, "service": service})
            missing_customer = [x for x in ("customer_name", "phone") if not str(arguments.get(x) or "").strip()]
            if missing_customer:
                return ToolResult(success=False, error="Missing customer fields: " + ", ".join(missing_customer))
            if conflict:
                return ToolResult(success=False, error="Requested booking time is not available", data={"available": False, "date": booking_date, "time": booking_time})
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
            return ToolResult(success=True, data={"action": "booking_created", "booking_id": booking.id, "status": "confirmed", "date": booking.booking_date, "time": booking.booking_time, "service": booking.service})

        bid = arguments.get("booking_id")
        if not bid:
            return ToolResult(success=False, error="booking_id is required")
        booking = db.query(Booking).filter(Booking.id == bid, Booking.company_id == cid, Booking.agent_id == aid).first()
        if not booking:
            return ToolResult(success=False, error="Booking not found")
        if action == "cancel":
            if booking.status == "cancelled":
                return ToolResult(success=True, data={"action": "booking_cancelled", "booking_id": booking.id, "already_cancelled": True})
            booking.status = "cancelled"
            db.flush()
            return ToolResult(success=True, data={"action": "booking_cancelled", "booking_id": booking.id})
        if action == "reschedule":
            new_date = str(arguments.get("date") or booking.booking_date).strip()
            new_time = str(arguments.get("time") or booking.booking_time).strip()
            if not _valid_iso_date(new_date) or not _valid_iso_time(new_time):
                return ToolResult(success=False, error="Reschedule date/time must use YYYY-MM-DD and HH:MM")
            conflict = (
                db.query(Booking)
                .filter(
                    Booking.company_id == cid,
                    Booking.booking_date == new_date,
                    Booking.booking_time == new_time,
                    Booking.status.in_(["pending", "confirmed"]),
                    Booking.id != booking.id,
                )
                .first()
            )
            if conflict:
                return ToolResult(success=False, error="Requested booking time is not available", data={"available": False, "date": new_date, "time": new_time})
            booking.booking_date = new_date
            booking.booking_time = new_time
            booking.status = "confirmed"
            db.flush()
            return ToolResult(success=True, data={"action": "booking_rescheduled", "booking_id": booking.id, "date": booking.booking_date, "time": booking.booking_time})
        return ToolResult(success=False, error="Invalid booking action")


class OrderTool(AgentTool):
    name = "order"
    description = "Create and save a real customer order in Xvond. Every requested item must exist in company knowledge. Never confirm unless this tool returns success."
    input_schema = {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string"},
            "phone": {"type": "string"},
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1, "maximum": 100},
                        "variant": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["name", "quantity"],
                    "additionalProperties": False,
                },
            },
            "delivery_address": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["items"],
        "additionalProperties": False,
    }

    def execute(self, arguments, context):
        db = context["db"]
        cid = context["company_id"]
        aid = context["agent_id"]
        raw_items = arguments.get("items") or []
        if not isinstance(raw_items, list) or not raw_items:
            return ToolResult(success=False, error="Order requires at least one item")
        items = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                return ToolResult(success=False, error="Each order item must be structured")
            name = str(raw.get("name") or "").strip()
            try:
                quantity = int(raw.get("quantity"))
            except Exception:
                quantity = 0
            if not name or quantity < 1 or quantity > 100:
                return ToolResult(success=False, error="Each item requires a valid name and quantity")
            if not _known_business_item(db, cid, aid, name):
                return ToolResult(success=False, error=f"Order item is not present in company knowledge: {name}")
            item = {"name": name, "quantity": quantity}
            if str(raw.get("variant") or "").strip():
                item["variant"] = str(raw["variant"]).strip()
            if str(raw.get("notes") or "").strip():
                item["notes"] = str(raw["notes"]).strip()
            items.append(item)
        order = Order(
            company_id=cid,
            agent_id=aid,
            customer_name=str(arguments.get("customer_name") or "").strip() or None,
            phone=str(arguments.get("phone") or "").strip() or None,
            items=items,
            delivery_address=str(arguments.get("delivery_address") or "").strip() or None,
            notes=str(arguments.get("notes") or "").strip() or None,
        )
        db.add(order)
        db.flush()
        return ToolResult(success=True, data={"action": "order_created", "order_id": order.id, "status": order.status, "items": items})


class HumanHandoffTool(AgentTool):
    name = "human_handoff"
    description = "Escalate a conversation to a human employee and pause AI replies for that WhatsApp conversation."
    input_schema = {"type": "object", "properties": {"reason": {"type": "string"}, "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]}, "department": {"type": "string"}}, "additionalProperties": False}

    def execute(self, arguments, context):
        db = context["db"]
        conversation_id = context.get("conversation_id")
        reason = arguments.get("reason") or "ai_handoff"
        handoff = HumanHandoff(company_id=context["company_id"], agent_id=context["agent_id"], conversation_id=conversation_id, reason=reason, priority=arguments.get("priority", "normal"), department=arguments.get("department", context.get("config", {}).get("department", "customer_service")))
        db.add(handoff)
        db.flush()
        session = None
        if conversation_id is not None:
            session = db.query(WhatsAppSession).filter(WhatsAppSession.company_id == context["company_id"], WhatsAppSession.agent_id == context["agent_id"], WhatsAppSession.conversation_id == conversation_id).first()
            if session is not None:
                activate_human_handoff(session, reason=reason)
        return ToolResult(success=True, data={"action": "human_handoff_created", "handoff_id": handoff.id, "status": handoff.status, "ai_paused": session is not None})


class WebhookTool(AgentTool):
    name = "webhook"
    description = "Send data to an external webhook."
    input_schema = {"type": "object", "properties": {"payload": {"type": "object"}}, "additionalProperties": True}

    def execute(self, arguments, context):
        config = context.get("config", {}) or {}
        url = config.get("url")
        if not url:
            return ToolResult(success=False, error="Webhook URL is not configured")
        try:
            validate_public_http_url(url)
            result = safe_http_request(url=url, method=config.get("method", "POST"), headers={"Content-Type": "application/json", **(config.get("headers", {}) or {})}, json_data=arguments.get("payload", arguments), timeout=config.get("timeout", 15))
            status = int(result["status_code"])
            return ToolResult(success=200 <= status < 300, data=result, error=None if 200 <= status < 300 else f"Webhook returned HTTP {status}")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class CustomAPITool(AgentTool):
    name = "custom_api"
    description = "Call a configured external business API."
    input_schema = {"type": "object", "properties": {"endpoint": {"type": "string"}, "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]}, "payload": {}}, "additionalProperties": False}

    def execute(self, arguments, context):
        config = context.get("config", {}) or {}
        base_url = config.get("base_url")
        if not base_url:
            return ToolResult(success=False, error="API base_url is not configured")
        endpoint = str(arguments.get("endpoint", "") or "").strip()
        lowered = endpoint.lower()
        if lowered.startswith("http://") or lowered.startswith("https://") or endpoint.startswith("//"):
            return ToolResult(success=False, error="API endpoint must be a relative path")
        url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
        try:
            validate_public_http_url(base_url)
            validate_public_http_url(url)
            headers = {"Content-Type": "application/json", **(config.get("headers", {}) or {})}
            api_key = config.get("api_key")
            if api_key and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {api_key}"
            result = safe_http_request(url=url, method=arguments.get("method", "POST"), headers=headers, json_data=arguments.get("payload"), timeout=config.get("timeout", 15))
            status = int(result["status_code"])
            return ToolResult(success=200 <= status < 300, data=result, error=None if 200 <= status < 300 else f"External API returned HTTP {status}")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


BUILTIN_TOOLS = [LeadTool(), BookingTool(), OrderTool(), HumanHandoffTool(), WebhookTool(), CustomAPITool()]
