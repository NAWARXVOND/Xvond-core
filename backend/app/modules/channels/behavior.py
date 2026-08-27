def build_text_channel_behavior_prompt(
    channel_type: str,
    config: dict | None = None,
) -> str:
    config = config or {}
    channel_type = str(channel_type or "").strip().lower()
    language = str(config.get("language") or "auto").strip()
    dialect = str(config.get("dialect") or "auto").strip()
    tone = str(config.get("tone") or "professional_friendly").strip()
    response_style = str(config.get("response_style") or "conversational").strip()
    response_length = str(config.get("response_length") or "concise").strip()
    instructions = str(config.get("channel_instructions") or "").strip()
    emoji_style = str(config.get("emoji_style") or "minimal").strip()

    parts = [
        f"{channel_type.upper()} CHANNEL BEHAVIOR:",
        f"Language: {language}.",
        f"Dialect: {dialect}.",
        f"Tone: {tone}.",
        f"Response style: {response_style}.",
        f"Response length: {response_length}.",
    ]
    if channel_type == "whatsapp":
        parts.extend(
            [
                f"Emoji style: {emoji_style}.",
                "Write as a natural WhatsApp business conversation.",
                "Prefer short paragraphs and avoid unnecessary formatting.",
                "Do not send long lists unless the customer explicitly asks for them.",
            ]
        )
    if instructions:
        parts.append("Channel-specific instructions: " + instructions)
    return "\n".join(parts)
