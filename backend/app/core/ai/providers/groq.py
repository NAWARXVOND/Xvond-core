import json
from decimal import Decimal
from typing import Any

import httpx

from backend.app.core.ai.base import AIResponse, ToolCall, ToolOutput
from backend.app.core.ai.providers.openai import OpenAIProvider
from backend.app.core.config.settings import settings


class GroqProvider(OpenAIProvider):
    """Groq provider with native Chat Completions orchestration for local tools.

    Groq's Responses API does not support previous_response_id. Xvond agents need
    multi-round local tool calling, so this provider keeps the assistant tool-call
    message in continuation and sends tool results back using the documented
    Chat Completions tool protocol.
    """

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured")
        self.api_key = settings.GROQ_API_KEY

    def _request_url(self) -> str:
        return "https://api.groq.com/openai/v1/chat/completions"

    def _convert_chat_tools(self, tools: list[dict] | None) -> list[dict]:
        result = []
        for tool in tools or []:
            name = tool.get("name")
            if not name:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters") or tool.get("input_schema") or {"type": "object", "properties": {}},
                },
            })
        return result

    def _tool_messages(self, outputs: list[ToolOutput]) -> list[dict]:
        messages = []
        for output in outputs:
            payload: dict[str, Any] = {"success": output.success}
            if output.data is not None:
                payload["data"] = output.data
            if output.error:
                payload["error"] = output.error
            messages.append({
                "role": "tool",
                "tool_call_id": output.call_id,
                "name": output.name,
                "content": json.dumps(payload, ensure_ascii=False, default=str),
            })
        return messages

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        tools: list[dict] | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        continuation: Any = None,
    ) -> AIResponse:
        converted_tools = self._convert_chat_tools(tools)
        messages = [{"role": "system", "content": system_prompt}]

        if continuation and tool_outputs:
            previous_messages = continuation.get("messages") if isinstance(continuation, dict) else None
            if not previous_messages:
                raise RuntimeError("Groq tool continuation is missing conversation state")
            messages.extend(previous_messages)
            messages.extend(self._tool_messages(tool_outputs))
        else:
            messages.append({"role": "user", "content": user_message})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        if converted_tools:
            payload["tools"] = converted_tools
            payload["tool_choice"] = "auto"
            # gpt-oss-20b supports local tool use but not parallel tool calls.
            payload["parallel_tool_calls"] = False

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    self._request_url(),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Groq connection failed: {exc}") from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = (error_data.get("error") or {}).get("message")
            except Exception:
                message = response.text
            raise RuntimeError(f"Groq request failed ({response.status_code}): {message or 'Unknown error'}")

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Groq returned no completion choice")
        message = choices[0].get("message") or {}
        text = str(message.get("content") or "").strip()
        tool_calls = []

        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            name = str(function.get("name") or "")
            call_id = str(item.get("id") or "")
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {}
            if name and call_id:
                tool_calls.append(ToolCall(id=call_id, name=name, arguments=arguments if isinstance(arguments, dict) else {}))

        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)

        continuation_messages = None
        if tool_calls:
            assistant_tool_message = {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": message.get("tool_calls") or [],
            }
            # The first request always contains the complete grounded runtime user
            # message. Retain it plus each assistant/tool turn for the next round.
            continuation_messages = list(messages[1:]) + [assistant_tool_message]

        return AIResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=Decimal("0"),
            tool_calls=tool_calls,
            continuation={"messages": continuation_messages} if continuation_messages is not None else None,
        )
