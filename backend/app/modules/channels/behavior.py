def _clean(value, default="") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def build_channel_behavior_prompt(
    channel_type: str,
    config: dict | None,
) -> str:
    """Build channel-specific response instructions without changing agent knowledge."""
    config = config or {}
    channel_type = _clean(channel_type, "unknown").lower()

    language = _clean(config.get("language"), "auto")
    dialect = _clean(config.get("dialect"), "auto")
    tone = _clean(config.get("tone"), "professional_friendly")
    response_length = _clean(config.get("response_length"), "concise")
    response_style = _clean(config.get("response_style"), "natural")
    custom = _clean(config.get("channel_instructions"))

    instructions = [
        f"CHANNEL: {channel_type}",
        f"RESPONSE LANGUAGE: {language}",
        f"DIALECT: {dialect}",
        f"TONE: {tone}",
        f"RESPONSE STYLE: {response_style}",
        f"RESPONSE LENGTH: {response_length}",
    ]

    if language == "auto":
        instructions.append(
            "Match the customer's language unless the channel configuration says otherwise."
        )

    if dialect == "auto":
        instructions.append(
            "Match the customer's natural dialect when it can be inferred reliably; otherwise use neutral language."
        )
    else:
        instructions.append(
            "Use the configured dialect naturally. Do not exaggerate slang or imitate stereotypes."
        )

    if channel_type == "voice":
        instructions.extend([
            "Write responses for speech, not for reading.",
            "Keep sentences short and easy to understand when heard once.",
            "Do not read long URLs, markup, tables, or large lists aloud.",
        ])
    elif channel_type == "whatsapp":
        emoji_style = _clean(config.get("emoji_style"), "minimal")
        instructions.extend([
            f"EMOJI STYLE: {emoji_style}",
            "Prefer short chat-sized messages and clear formatting.",
        ])

    if custom:
        instructions.append("CHANNEL-SPECIFIC INSTRUCTIONS:\n" + custom)

    return "\n".join(instructions)
