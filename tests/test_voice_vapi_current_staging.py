from pathlib import Path

import pytest

from backend.app.modules.channels.vapi import (
    build_vapi_assistant_payload,
    build_voice_behavior_prompt,
    normalize_vapi_messages,
)


def test_voice_behavior_is_channel_specific_and_spoken():
    prompt = build_voice_behavior_prompt(
        {
            "language": "ar",
            "dialect": "omani",
            "tone": "warm",
            "channel_instructions": "Do not read long price lists aloud.",
        }
    )
    assert "VOICE CHANNEL BEHAVIOR" in prompt
    assert "Language: ar" in prompt
    assert "Dialect: omani" in prompt
    assert "Tone: warm" in prompt
    assert "Write for speech" in prompt
    assert "Do not read long price lists aloud" in prompt


def test_vapi_payload_points_back_to_xvond_and_correlates_call_id():
    payload = build_vapi_assistant_payload(
        assistant_name="Reception",
        model_url="https://api.xvond.com/v1/voice/7/chat/completions",
        channel_config={
            "language": "ar",
            "voice_id": "voice-1",
            "greeting_message": "مرحبا",
            "allow_interruption": True,
        },
        credential_id="cred-1",
    )
    assert payload["model"]["provider"] == "custom-llm"
    assert payload["model"]["credentialId"] == "cred-1"
    assert payload["model"]["headers"]["X-Xvond-Call-Id"] == "{{call.id}}"
    assert payload["model"]["url"].endswith("/v1/voice/7/chat/completions")
    assert payload["voice"]["voiceId"] == "voice-1"
    assert payload["firstMessage"] == "مرحبا"


def test_normalize_vapi_messages_uses_latest_caller_message():
    prior, latest = normalize_vapi_messages(
        [
            {"role": "user", "content": "مرحبا"},
            {"role": "assistant", "content": "أهلا"},
            {"role": "user", "content": "بدي أحجز"},
        ]
    )
    assert latest == "بدي أحجز"
    assert "مرحبا" in prior
    assert "أهلا" in prior


def test_normalize_vapi_messages_rejects_missing_caller_message():
    with pytest.raises(ValueError):
        normalize_vapi_messages([{"role": "assistant", "content": "Hello"}])


def test_current_admin_loads_voice_controls_without_replacing_workspace():
    root = Path(__file__).resolve().parents[1]
    index = (root / "frontend" / "admin" / "index.html").read_text(encoding="utf-8-sig")
    voice = (root / "frontend" / "admin" / "voice-admin.js").read_text(encoding="utf-8-sig")
    assert "/static/admin/company-control-center.js" in index
    assert "/static/admin/voice-admin.js" in index
    assert "renderChannelsTab" in voice
    assert "/admin/voice/vapi/phone-numbers" in voice
    assert "/vapi/provision" in voice
