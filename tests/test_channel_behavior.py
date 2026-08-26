from backend.app.modules.channels.behavior import build_channel_behavior_prompt


def test_whatsapp_dialect_behavior_is_configurable():
    prompt = build_channel_behavior_prompt(
        "whatsapp",
        {
            "language": "ar",
            "dialect": "omani",
            "tone": "friendly",
            "response_length": "short",
            "emoji_style": "minimal",
        },
    )

    assert "RESPONSE LANGUAGE: ar" in prompt
    assert "DIALECT: omani" in prompt
    assert "TONE: friendly" in prompt
    assert "EMOJI STYLE: minimal" in prompt


def test_voice_behavior_is_distinct_from_text_channels():
    prompt = build_channel_behavior_prompt(
        "voice",
        {
            "language": "ar",
            "dialect": "gulf",
            "tone": "professional_friendly",
            "response_length": "short",
        },
    )

    assert "DIALECT: gulf" in prompt
    assert "Write responses for speech" in prompt
    assert "Do not read long URLs" in prompt
