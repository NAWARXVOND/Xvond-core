from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VapiAssistantConfig:
    name: str
    model_url: str
    first_message: str | None
    language: str
    voice_id: str | None
    allow_interruption: bool


def build_vapi_assistant_payload(
    *,
    assistant_name: str,
    model_url: str,
    channel_config: dict | None = None,
    credential_id: str | None = None,
) -> dict:
    """Build a Vapi assistant that keeps Xvond as the LLM/business-logic layer.

    Vapi handles telephony, transcription and speech synthesis. The model points
    back to Xvond's OpenAI-compatible voice endpoint, so knowledge and tools stay
    inside Xvond.
    """
    config = channel_config or {}

    language = str(config.get("language") or "auto").strip()
    voice_id = str(config.get("voice_id") or "").strip() or None
    greeting = str(config.get("greeting_message") or "").strip() or None
    allow_interruption = bool(config.get("allow_interruption", True))

    model = {
        "provider": "custom-llm",
        "model": "xvond-agent",
        "url": model_url,
    }

    if credential_id:
        model["credentialId"] = credential_id

    voice = {
        "provider": "vapi",
        "version": 2,
    }
    if voice_id:
        voice["voiceId"] = voice_id
    if language and language != "auto":
        voice["language"] = language
    else:
        voice["language"] = "auto"

    transcriber = {
        "provider": "openai",
        "model": "gpt-4o-mini-transcribe",
    }
    if language and language != "auto":
        transcriber["language"] = language

    payload = {
        "name": assistant_name,
        "model": model,
        "voice": voice,
        "transcriber": transcriber,
        "stopSpeakingPlan": {
            "numWords": 2 if allow_interruption else 8,
        },
    }

    if greeting:
        payload["firstMessage"] = greeting

    return payload


def normalize_vapi_messages(messages: list[dict] | None) -> tuple[str, str]:
    """Return prior voice context and the latest caller message."""
    items = messages or []
    latest_user = ""
    context_lines: list[str] = []

    for item in items:
        role = str(item.get("role") or "").strip().lower()
        content = item.get("content")

        if isinstance(content, list):
            content = " ".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict)
            )

        text = str(content or "").strip()
        if not text:
            continue

        if role == "user":
            latest_user = text

        if role in {"user", "assistant"}:
            context_lines.append(f"{role}: {text}")

    if not latest_user:
        raise ValueError("Vapi request does not contain a caller message")

    prior = "\n".join(context_lines[:-1]) if len(context_lines) > 1 else ""
    return prior[-10000:], latest_user
