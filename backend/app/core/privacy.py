import re
from dataclasses import dataclass
from typing import Any

from backend.app.core.ai.base import AIResponse, ToolCall, ToolOutput


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
_HIGH_CONFIDENCE_ID_RE = re.compile(r"(?<!\d)\d{8,12}(?!\d)")


@dataclass(frozen=True)
class ProtectedText:
    text: str
    replacements: dict[str, str]


def _replace_matches(
    text: str,
    pattern: re.Pattern,
    label: str,
    replacements: dict[str, str],
) -> str:
    counter = 0

    def repl(match: re.Match) -> str:
        nonlocal counter
        original = match.group(0)
        for token, stored in replacements.items():
            if stored == original:
                return token
        counter += 1
        token = f"[XVOND_{label}_{counter}]"
        while token in replacements:
            counter += 1
            token = f"[XVOND_{label}_{counter}]"
        replacements[token] = original
        return token

    return pattern.sub(repl, text)


def protect_text(
    text: str,
    replacements: dict[str, str] | None = None,
) -> ProtectedText:
    mapping = replacements if replacements is not None else {}
    protected = str(text or "")
    protected = _replace_matches(protected, _EMAIL_RE, "EMAIL", mapping)
    protected = _replace_matches(protected, _PHONE_RE, "PHONE", mapping)
    protected = _replace_matches(protected, _HIGH_CONFIDENCE_ID_RE, "ID", mapping)
    return ProtectedText(text=protected, replacements=mapping)


def protect_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return protect_text(value, replacements).text
    if isinstance(value, list):
        return [protect_value(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(protect_value(item, replacements) for item in value)
    if isinstance(value, dict):
        return {key: protect_value(item, replacements) for key, item in value.items()}
    return value


def protect_tool_outputs(
    outputs: list[ToolOutput] | None,
    replacements: dict[str, str],
) -> list[ToolOutput] | None:
    if outputs is None:
        return None
    return [
        ToolOutput(
            call_id=item.call_id,
            name=item.name,
            success=item.success,
            data=protect_value(item.data, replacements),
            error=protect_value(item.error, replacements),
        )
        for item in outputs
    ]


def restore_text(text: str, replacements: dict[str, str]) -> str:
    restored = str(text or "")
    for token, original in replacements.items():
        restored = restored.replace(token, original)
    return restored


def restore_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return restore_text(value, replacements)
    if isinstance(value, list):
        return [restore_value(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(restore_value(item, replacements) for item in value)
    if isinstance(value, dict):
        return {key: restore_value(item, replacements) for key, item in value.items()}
    return value


def restore_ai_response(response: AIResponse, replacements: dict[str, str]) -> AIResponse:
    if not replacements:
        return response
    response.text = restore_text(response.text, replacements)
    response.tool_calls = [
        ToolCall(
            id=call.id,
            name=call.name,
            arguments=restore_value(call.arguments, replacements),
        )
        for call in response.tool_calls
    ]
    return response
