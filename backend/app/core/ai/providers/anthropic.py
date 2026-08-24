
import json
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


class AnthropicProvider(AIProvider):

    def __init__(self):

        if not settings.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not configured"
            )

        self.api_key = settings.ANTHROPIC_API_KEY

    def _tools(
        self,
        tools: list[dict] | None,
    ) -> list[dict]:

        result = []

        for tool in tools or []:

            name = tool.get("name")

            if not name:
                continue

            result.append({
                "name": name,
                "description": tool.get(
                    "description",
                    "",
                ),
                "input_schema": (
                    tool.get("parameters")
                    or tool.get("input_schema")
                    or {
                        "type": "object",
                        "properties": {},
                    }
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

        converted_tools = self._tools(
            tools
        )

        if continuation and tool_outputs:

            previous_content = (
                continuation.get(
                    "content",
                    [],
                )
                if isinstance(
                    continuation,
                    dict,
                )
                else []
            )

            results = []

            for output in tool_outputs:

                value = {
                    "success":
                        output.success,
                    "data":
                        output.data,
                }

                if output.error:
                    value["error"] = (
                        output.error
                    )

                results.append({
                    "type":
                        "tool_result",
                    "tool_use_id":
                        output.call_id,
                    "content":
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            default=str,
                        ),
                    "is_error":
                        not output.success,
                })

            messages = [
                {
                    "role": "assistant",
                    "content":
                        previous_content,
                },
                {
                    "role": "user",
                    "content": results,
                },
            ]

        else:

            messages = [{
                "role": "user",
                "content": user_message,
            }]

        payload = {
            "model": model,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": messages,
        }

        if converted_tools:
            payload["tools"] = (
                converted_tools
            )

        try:

            with httpx.Client(
                timeout=120.0,
            ) as client:

                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key":
                            self.api_key,
                        "anthropic-version":
                            "2023-06-01",
                        "content-type":
                            "application/json",
                    },
                    json=payload,
                )

        except httpx.HTTPError as exc:

            raise RuntimeError(
                "Anthropic connection failed: "
                f"{exc}"
            ) from exc

        if response.status_code >= 400:

            try:
                error = response.json()
            except Exception:
                error = response.text

            raise RuntimeError(
                "Anthropic request failed "
                f"({response.status_code}): "
                f"{error}"
            )

        data = response.json()

        text_parts = []
        calls = []

        for block in data.get(
            "content",
            [],
        ):

            block_type = block.get(
                "type"
            )

            if block_type == "text":

                value = block.get(
                    "text",
                    "",
                )

                if value:
                    text_parts.append(value)

            elif block_type == "tool_use":

                call_id = block.get(
                    "id",
                    "",
                )

                name = block.get(
                    "name",
                    "",
                )

                if call_id and name:

                    calls.append(
                        ToolCall(
                            id=call_id,
                            name=name,
                            arguments=(
                                block.get(
                                    "input"
                                )
                                or {}
                            ),
                        )
                    )

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

        return AIResponse(
            text="\n".join(
                text_parts
            ).strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(
                input_tokens
                + output_tokens
            ),
            cost=Decimal("0"),
            tool_calls=calls,
            continuation={
                "content":
                    data.get(
                        "content",
                        [],
                    )
            },
        )
