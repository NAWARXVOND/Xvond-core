
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


class GoogleProvider(AIProvider):

    def __init__(self):

        if not settings.GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY is not configured"
            )

        self.api_key = settings.GOOGLE_API_KEY

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
                "type": "function",
                "name": name,
                "description": tool.get(
                    "description",
                    "",
                ),
                "parameters": (
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

        payload: dict[str, Any] = {
            "model": model,
        }

        if continuation and tool_outputs:

            payload[
                "previous_interaction_id"
            ] = continuation

            inputs = []

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

                inputs.append({
                    "type":
                        "function_result",
                    "name":
                        output.name,
                    "call_id":
                        output.call_id,
                    "result": [{
                        "type": "text",
                        "text":
                            json.dumps(
                                value,
                                ensure_ascii=False,
                                default=str,
                            ),
                    }],
                })

            payload["input"] = inputs

        else:

            payload["input"] = (
                user_message
            )

        if system_prompt:

            payload[
                "system_instruction"
            ] = system_prompt

        if converted_tools:

            payload["tools"] = (
                converted_tools
            )

        try:

            with httpx.Client(
                timeout=120.0,
            ) as client:

                response = client.post(
                    "https://generativelanguage.googleapis.com/v1beta/interactions",
                    headers={
                        "x-goog-api-key":
                            self.api_key,
                        "Content-Type":
                            "application/json",
                    },
                    json=payload,
                )

        except httpx.HTTPError as exc:

            raise RuntimeError(
                "Google AI connection failed: "
                f"{exc}"
            ) from exc

        if response.status_code >= 400:

            try:
                error = response.json()
            except Exception:
                error = response.text

            raise RuntimeError(
                "Google AI request failed "
                f"({response.status_code}): "
                f"{error}"
            )

        data = response.json()

        text_parts = []
        calls = []

        for step in data.get(
            "steps",
            [],
        ):

            step_type = step.get(
                "type"
            )

            if step_type == "function_call":

                call_id = step.get(
                    "id",
                    "",
                )

                name = step.get(
                    "name",
                    "",
                )

                if call_id and name:

                    calls.append(
                        ToolCall(
                            id=call_id,
                            name=name,
                            arguments=(
                                step.get(
                                    "arguments"
                                )
                                or {}
                            ),
                        )
                    )

            content = step.get(
                "content"
            )

            if isinstance(
                content,
                list,
            ):

                for part in content:

                    if not isinstance(
                        part,
                        dict,
                    ):
                        continue

                    value = part.get(
                        "text"
                    )

                    if value:
                        text_parts.append(
                            value
                        )

            elif isinstance(
                content,
                str,
            ):

                if content:
                    text_parts.append(
                        content
                    )

        if (
            not text_parts
            and data.get("output_text")
        ):
            text_parts.append(
                data["output_text"]
            )

        usage = (
            data.get("usage")
            or data.get(
                "usage_metadata"
            )
            or {}
        )

        input_tokens = int(
            usage.get(
                "total_input_tokens",
                usage.get(
                    "input_tokens",
                    usage.get(
                        "prompt_token_count",
                        0,
                    ),
                ),
            )
            or 0
        )

        output_tokens = int(
            usage.get(
                "total_output_tokens",
                usage.get(
                    "output_tokens",
                    usage.get(
                        "candidates_token_count",
                        0,
                    ),
                ),
            )
            or 0
        )

        total_tokens = int(
            usage.get(
                "total_tokens",
                usage.get(
                    "total_token_count",
                    input_tokens
                    + output_tokens,
                ),
            )
            or 0
        )

        return AIResponse(
            text="\n".join(
                text_parts
            ).strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=Decimal("0"),
            tool_calls=calls,
            continuation=data.get(
                "id"
            ),
        )
