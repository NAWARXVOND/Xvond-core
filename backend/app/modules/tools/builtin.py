import json
import urllib.request

from backend.app.core.http_security import (
    safe_http_request,
    validate_public_http_url,
)

from backend.app.modules.tools.base import (
    AgentTool,
    ToolResult,
)

from backend.app.modules.tools.business_models import (
    Lead,
    Booking,
    Order,
    HumanHandoff,
)


class LeadTool(AgentTool):
    name = "lead"
    description = "Capture and save a customer lead."

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

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

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
            data={
                "action": "lead_created",
                "lead_id": lead.id,
                "status": lead.status,
            },
        )


class BookingTool(AgentTool):
    name = "booking"
    description = "Create, reschedule or cancel bookings."

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create",
                    "reschedule",
                    "cancel",
                ],
            },
            "booking_id": {
                "type": "integer"
            },
            "customer_name": {
                "type": "string"
            },
            "phone": {
                "type": "string"
            },
            "service": {
                "type": "string"
            },
            "date": {
                "type": "string"
            },
            "time": {
                "type": "string"
            },
        },
        "additionalProperties": False,
    }

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

        db = context["db"]

        action = arguments.get(
            "action",
            "create",
        )

        if action == "create":

            booking = Booking(
                company_id=context["company_id"],
                agent_id=context["agent_id"],
                customer_name=arguments.get(
                    "customer_name"
                ),
                phone=arguments.get("phone"),
                service=arguments.get("service"),
                booking_date=arguments.get("date"),
                booking_time=arguments.get("time"),
                status="confirmed",
            )

            db.add(booking)
            db.flush()

            return ToolResult(
                success=True,
                data={
                    "action": "booking_created",
                    "booking_id": booking.id,
                    "status": booking.status,
                },
            )

        booking_id = arguments.get(
            "booking_id"
        )

        if not booking_id:
            return ToolResult(
                success=False,
                error="booking_id is required",
            )

        booking = (
            db.query(Booking)
            .filter(
                Booking.id == booking_id,
                Booking.company_id
                == context["company_id"],
                Booking.agent_id
                == context["agent_id"],
            )
            .first()
        )

        if booking is None:
            return ToolResult(
                success=False,
                error="Booking not found",
            )

        if action == "cancel":

            booking.status = "cancelled"
            db.flush()

            return ToolResult(
                success=True,
                data={
                    "action": "booking_cancelled",
                    "booking_id": booking.id,
                },
            )

        if action == "reschedule":

            if arguments.get("date"):
                booking.booking_date = (
                    arguments["date"]
                )

            if arguments.get("time"):
                booking.booking_time = (
                    arguments["time"]
                )

            booking.status = "confirmed"

            db.flush()

            return ToolResult(
                success=True,
                data={
                    "action":
                        "booking_rescheduled",
                    "booking_id": booking.id,
                    "date":
                        booking.booking_date,
                    "time":
                        booking.booking_time,
                },
            )

        return ToolResult(
            success=False,
            error="Invalid booking action",
        )


class OrderTool(AgentTool):
    name = "order"
    description = "Create and save customer orders."

    input_schema = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string"
            },
            "phone": {
                "type": "string"
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object"
                },
                "minItems": 1,
            },
            "delivery_address": {
                "type": "string"
            },
            "notes": {
                "type": "string"
            },
        },
        "required": [
            "items"
        ],
        "additionalProperties": False,
    }

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

        db = context["db"]

        items = arguments.get(
            "items",
            [],
        )

        if not items:
            return ToolResult(
                success=False,
                error="Order requires items",
            )

        order = Order(
            company_id=context["company_id"],
            agent_id=context["agent_id"],
            customer_name=arguments.get(
                "customer_name"
            ),
            phone=arguments.get("phone"),
            items=items,
            delivery_address=arguments.get(
                "delivery_address"
            ),
            notes=arguments.get("notes"),
        )

        db.add(order)
        db.flush()

        return ToolResult(
            success=True,
            data={
                "action": "order_created",
                "order_id": order.id,
                "status": order.status,
            },
        )


class HumanHandoffTool(AgentTool):
    name = "human_handoff"
    description = "Escalate a conversation to a human employee."

    input_schema = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string"
            },
            "priority": {
                "type": "string",
                "enum": [
                    "low",
                    "normal",
                    "high",
                    "urgent",
                ],
            },
            "department": {
                "type": "string"
            },
        },
        "additionalProperties": False,
    }

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

        db = context["db"]

        handoff = HumanHandoff(
            company_id=context["company_id"],
            agent_id=context["agent_id"],
            conversation_id=context.get(
                "conversation_id"
            ),
            reason=arguments.get("reason"),
            priority=arguments.get(
                "priority",
                "normal",
            ),
            department=arguments.get(
                "department",
                context.get(
                    "config",
                    {},
                ).get(
                    "department",
                    "customer_service",
                ),
            ),
        )

        db.add(handoff)
        db.flush()

        return ToolResult(
            success=True,
            data={
                "action":
                    "human_handoff_created",
                "handoff_id": handoff.id,
                "status": handoff.status,
            },
        )



class WebhookTool(AgentTool):
    name = "webhook"
    description = (
        "Send data to an external webhook."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object"
            },
        },
        "additionalProperties": True,
    }

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

        config = (
            context.get(
                "config",
                {},
            )
            or {}
        )

        url = config.get(
            "url"
        )

        if not url:
            return ToolResult(
                success=False,
                error=(
                    "Webhook URL is not configured"
                ),
            )

        try:

            validate_public_http_url(
                url
            )

            payload = (
                arguments.get(
                    "payload",
                    arguments,
                )
            )

            result = (
                safe_http_request(
                    url=url,
                    method=config.get(
                        "method",
                        "POST",
                    ),
                    headers={
                        "Content-Type":
                            "application/json",
                        **(
                            config.get(
                                "headers",
                                {},
                            )
                            or {}
                        ),
                    },
                    json_data=payload,
                    timeout=config.get(
                        "timeout",
                        15,
                    ),
                )
            )

            status = int(
                result[
                    "status_code"
                ]
            )

            if (
                status < 200
                or status >= 300
            ):
                return ToolResult(
                    success=False,
                    error=(
                        "Webhook returned "
                        f"HTTP {status}"
                    ),
                    data=result,
                )

            return ToolResult(
                success=True,
                data=result,
            )

        except Exception as exc:

            return ToolResult(
                success=False,
                error=str(exc),
            )


class CustomAPITool(AgentTool):
    name = "custom_api"
    description = (
        "Call a configured external business API."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string"
            },
            "method": {
                "type": "string",
                "enum": [
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                ],
            },
            "payload": {},
        },
        "additionalProperties": False,
    }

    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:

        config = (
            context.get(
                "config",
                {},
            )
            or {}
        )

        base_url = (
            config.get(
                "base_url"
            )
        )

        if not base_url:

            return ToolResult(
                success=False,
                error=(
                    "API base_url "
                    "is not configured"
                ),
            )

        endpoint = str(
            arguments.get(
                "endpoint",
                "",
            )
            or ""
        ).strip()

        # Endpoint may only be a relative
        # path. It cannot replace base host.
        lowered = endpoint.lower()

        if (
            lowered.startswith(
                "http://"
            )
            or lowered.startswith(
                "https://"
            )
            or endpoint.startswith(
                "//"
            )
        ):
            return ToolResult(
                success=False,
                error=(
                    "API endpoint must "
                    "be a relative path"
                ),
            )

        url = (
            base_url.rstrip("/")
            + "/"
            + endpoint.lstrip("/")
        )

        try:

            validate_public_http_url(
                base_url
            )

            validate_public_http_url(
                url
            )

            headers = {
                "Content-Type":
                    "application/json",
                **(
                    config.get(
                        "headers",
                        {},
                    )
                    or {}
                ),
            }

            api_key = config.get(
                "api_key"
            )

            if (
                api_key
                and "Authorization"
                not in headers
            ):
                headers[
                    "Authorization"
                ] = (
                    f"Bearer {api_key}"
                )

            result = (
                safe_http_request(
                    url=url,
                    method=arguments.get(
                        "method",
                        "POST",
                    ),
                    headers=headers,
                    json_data=arguments.get(
                        "payload"
                    ),
                    timeout=config.get(
                        "timeout",
                        15,
                    ),
                )
            )

            status = int(
                result[
                    "status_code"
                ]
            )

            if (
                status < 200
                or status >= 300
            ):
                return ToolResult(
                    success=False,
                    error=(
                        "External API returned "
                        f"HTTP {status}"
                    ),
                    data=result,
                )

            return ToolResult(
                success=True,
                data=result,
            )

        except Exception as exc:

            return ToolResult(
                success=False,
                error=str(exc),
            )


BUILTIN_TOOLS = [
    LeadTool(),
    BookingTool(),
    OrderTool(),
    HumanHandoffTool(),
    WebhookTool(),
    CustomAPITool(),
]
