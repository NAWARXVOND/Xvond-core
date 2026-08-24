from decimal import Decimal
from typing import Any

import httpx

from backend.app.core.ai.base import (
    AIProvider,
    AIResponse,
    ToolCall,
    ToolOutput,
)
from backend.app.core.config.settings import settings


class OpenAIProvider(AIProvider):

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not configured"
            )

        self.api_key = settings.OPENAI_API_KEY

    def _request_url(self) -> str:
        return "https://api.openai.com/v1/responses"

    def _convert_tools(
        self,
        tools: list[dict] | None,
    ) -> list[dict]:
        result = []

        for tool in tools or []:
            name = tool.get("name")

            if not name:
                continue

            parameters = (
                tool.get("parameters")
                or tool.get("input_schema")
                or {
                    "type": "object",
                    "properties": {},
                }
            )

            result.append({
                "type": "function",
                "name": name,
                "description": tool.get(
                    "description",
                    "",
                ),
                "parameters": parameters,
            })

        return result

    def _tool_output_input(
        self,
        tool_outputs: list[ToolOutput],
    ) -> list[dict]:
        result = []

        for output in tool_outputs:
            payload: dict[str, Any] = {
                "success": output.success,
            }

            if output.data is not None:
                payload["data"] = output.data

            if output.error:
                payload["error"] = output.error

            import json

            result.append({
                "type": "function_call_output",
                "call_id": output.call_id,
                "output": json.dumps(
                    payload,
                    ensure_ascii=False,
                    default=str,
                ),
            })

        return result

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        tools: list[dict] | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        continuation: Any = None,
    ) -> AIResponse:

        payload: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
        }

        if continuation and tool_outputs:
            payload["previous_response_id"] = (
                continuation
            )
            payload["input"] = (
                self._tool_output_input(
                    tool_outputs
                )
            )
        else:
            payload["input"] = user_message

        converted_tools = self._convert_tools(
            tools
        )

        if converted_tools:
            payload["tools"] = converted_tools

        try:
            with httpx.Client(
                timeout=120.0,
            ) as client:
                response = client.post(
                    self._request_url(),
                    headers={
                        "Authorization":
                            f"Bearer {self.api_key}",
                        "Content-Type":
                            "application/json",
                    },
                    json=payload,
                )

        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"OpenAI connection failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = (
                    error_data
                    .get("error", {})
                    .get("message")
                )
            except Exception:
                message = response.text

            raise RuntimeError(
                "OpenAI request failed "
                f"({response.status_code}): "
                f"{message or 'Unknown error'}"
            )

        data = response.json()

        text_parts = []
        tool_calls = []

        for item in data.get("output", []):

            item_type = item.get("type")

            if item_type == "message":
                for content in item.get(
                    "content",
                    [],
                ):
                    if (
                        content.get("type")
                        == "output_text"
                    ):
                        value = content.get(
                            "text",
                            "",
                        )
                        if value:
                            text_parts.append(value)

            elif item_type == "function_call":
                name = item.get("name", "")
                call_id = (
                    item.get("call_id")
                    or item.get("id")
                    or ""
                )

                arguments = item.get(
                    "arguments",
                    {},
                )

                if isinstance(arguments, str):
                    import json

                    try:
                        arguments = json.loads(
                            arguments
                        )
                    except Exception:
                        arguments = {}

                if name and call_id:
                    tool_calls.append(
                        ToolCall(
                            id=call_id,
                            name=name,
                            arguments=arguments,
                        )
                    )

        text = "\n".join(
            text_parts
        ).strip()

        usage = data.get(
            "usage",
            {},
        ) or {}

        input_tokens = int(
            usage.get(
                "input_tokens",
                0,
            ) or 0
        )

        output_tokens = int(
            usage.get(
                "output_tokens",
                0,
            ) or 0
        )

        total_tokens = int(
            usage.get(
                "total_tokens",
                input_tokens + output_tokens,
            ) or 0
        )

        return AIResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=Decimal("0"),
            tool_calls=tool_calls,
            continuation=data.get("id"),
        )
