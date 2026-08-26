from backend.app.modules.channels.vapi import (
    build_vapi_assistant_payload,
    normalize_vapi_messages,
)


def test_vapi_payload_keeps_xvond_as_custom_llm():
    payload = build_vapi_assistant_payload(
        assistant_name="Reception",
        model_url="https://api.xvond.com/voice/vapi/12/chat/completions",
        credential_id="cred_123",
        channel_config={
            "language": "ar",
            "dialect": "omani",
            "voice_id": "Elliot",
            "greeting_message": "مرحبا، كيف أقدر أساعدك؟",
            "allow_interruption": True,
        },
    )

    assert payload["model"]["provider"] == "custom-llm"
    assert payload["model"]["url"].endswith("/chat/completions")
    assert payload["model"]["credentialId"] == "cred_123"
    assert payload["voice"]["provider"] == "vapi"
    assert payload["voice"]["language"] == "ar"
    assert payload["transcriber"]["language"] == "ar"
    assert payload["firstMessage"].startswith("مرحبا")


def test_normalize_vapi_messages_finds_latest_caller_turn():
    prior, latest = normalize_vapi_messages(
        [
            {"role": "user", "content": "مرحبا"},
            {"role": "assistant", "content": "أهلا وسهلا"},
            {"role": "user", "content": "بدي أحجز بكرا"},
        ]
    )

    assert "user: مرحبا" in prior
    assert "assistant: أهلا وسهلا" in prior
    assert latest == "بدي أحجز بكرا"
