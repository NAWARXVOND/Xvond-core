from backend.app.core.ai.base import (
    AIProvider,
    AIResponse,
    ToolCall,
    ToolOutput,
)


class MockProvider(AIProvider):

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        tools: list[dict] | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        continuation=None,
    ) -> AIResponse:

        # ----------------------------------------------------
        # Second pass: tool already executed.
        # Return the final assistant response.
        # ----------------------------------------------------

        if tool_outputs:

            output = tool_outputs[0]

            return AIResponse(
                text=(
                    "[MOCK FINAL RESPONSE] "
                    f"Tool {output.name} executed. "
                    f"Success: {output.success}"
                ),
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            )

        # ----------------------------------------------------
        # First pass: simulate tool selection.
        # Only call tools actually assigned to this agent.
        # ----------------------------------------------------

        available = {
            tool.get("name")
            for tool in (tools or [])
            if tool.get("name")
        }

        message = (
            user_message
            or ""
        ).lower()

        call = None

        if (
            "lead" in available
            and any(
                word in message
                for word in [
                    "lead",
                    "customer lead",
                    "new customer",
                    "save me",
                ]
            )
        ):
            call = ToolCall(
                id="mock_call_lead_1",
                name="lead",
                arguments={
                    "name":
                        "Runtime Test Customer",
                    "phone":
                        "99999999",
                    "email":
                        "runtime@test.local",
                    "interest":
                        "Agent Runtime Test",
                    "notes":
                        "Created through MockProvider.",
                },
            )

        elif (
            "booking" in available
            and any(
                word in message
                for word in [
                    "book",
                    "booking",
                    "appointment",
                    "reserve",
                ]
            )
        ):
            call = ToolCall(
                id="mock_call_booking_1",
                name="booking",
                arguments={
                    "action": "create",
                    "customer_name":
                        "Runtime Test Customer",
                    "customer_phone":
                        "99999999",
                    "service":
                        "Runtime Test",
                    "booking_time":
                        "2026-08-24T12:00:00",
                },
            )

        elif (
            "order" in available
            and any(
                word in message
                for word in [
                    "order",
                    "buy",
                    "purchase",
                ]
            )
        ):
            call = ToolCall(
                id="mock_call_order_1",
                name="order",
                arguments={
                    "customer_name":
                        "Runtime Test Customer",
                    "customer_phone":
                        "99999999",
                    "items": [
                        {
                            "name":
                                "Runtime Test Item",
                            "quantity": 1,
                        }
                    ],
                },
            )

        elif (
            "human_handoff" in available
            and any(
                word in message
                for word in [
                    "human",
                    "employee",
                    "person",
                    "agent please",
                ]
            )
        ):
            call = ToolCall(
                id="mock_call_handoff_1",
                name="human_handoff",
                arguments={
                    "reason":
                        "Runtime test handoff",
                },
            )

        if call is not None:

            return AIResponse(
                text="",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                tool_calls=[
                    call
                ],
                continuation={
                    "mock": True,
                    "call_id": call.id,
                },
            )

        # ----------------------------------------------------
        # Normal mock response
        # ----------------------------------------------------

        return AIResponse(
            text=(
                "[MOCK AI RESPONSE]\n\n"
                f"Model: {model}\n"
                f"User: {user_message}"
            ),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
