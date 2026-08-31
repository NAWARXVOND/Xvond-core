from __future__ import annotations


def build_voice_behavior_prompt(config: dict | None = None) -> str:
    config = config or {}
    legacy_language = str(config.get("language") or "auto").strip()
    legacy_dialect = str(config.get("dialect") or "auto").strip()
    tone = str(config.get("tone") or "professional_friendly").strip()
    response_length = str(config.get("response_length") or "concise").strip()
    extra = str(config.get("channel_instructions") or "").strip()

    parts = [
        "VOICE CHANNEL BEHAVIOR:",
        "Language and dialect are controlled by the AI Employee profile and must not be overridden by channel settings.",
        (
            "Deprecated voice-channel metadata only — NEVER use this to override the AI Employee profile: "
            f"Language: {legacy_language}. Dialect: {legacy_dialect}."
        ),
        "Write for speech, not for reading.",
        "Use short natural sentences that are easy to hear.",
        "Do not read long URLs, markdown, tables, or long lists aloud.",
        "If details are too long for a call, offer to send or provide them through another configured channel.",
        f"Tone: {tone}.",
        f"Response length: {response_length}.",
    ]
    if extra:
        parts.append("Voice-specific instructions: " + extra)
    return "\n".join(parts)


def build_vapi_assistant_payload(
    *,
    assistant_name: str,
    model_url: str,
    channel_config: dict | None = None,
    credential_id: str | None = None,
) -> dict:
    config = channel_config or {}
    # This is transport/speech-recognition metadata only. Runtime response language
    # remains authoritative in the AI Employee profile.
    language = str(config.get("language") or "auto").strip()
    voice_id = str(config.get("voice_id") or "").strip() or None
    greeting = str(config.get("greeting_message") or "").strip() or None
    allow_interruption = bool(config.get("allow_interruption", True))

    model = {
        "provider": "custom-llm",
        "model": "xvond-agent",
        "url": model_url,
        "headers": {"X-Xvond-Call-Id": "{{call.id}}"},
    }
    if credential_id:
        model["credentialId"] = credential_id

    voice = {"provider": "vapi", "version": 2, "language": language or "auto"}
    if voice_id:
        voice["voiceId"] = voice_id

    transcriber = {"provider": "openai", "model": "gpt-4o-mini-transcribe"}
    if language and language != "auto":
        transcriber["language"] = language

    payload = {
        "name": assistant_name,
        "model": model,
        "voice": voice,
        "transcriber": transcriber,
        "stopSpeakingPlan": {"numWords": 2 if allow_interruption else 8},
    }
    if greeting:
        payload["firstMessage"] = greeting
    return payload


def normalize_vapi_messages(messages: list[dict] | None) -> tuple[str, str]:
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
