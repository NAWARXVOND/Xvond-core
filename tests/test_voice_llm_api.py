import pytest
from fastapi import HTTPException

from backend.app.api import voice_llm


class FakeChannel:
    config = {"llm_api_key": "secret-voice-key"}


def test_voice_llm_authentication_accepts_matching_bearer(monkeypatch):
    monkeypatch.setattr(
        voice_llm,
        "reveal_config",
        lambda value: value,
    )

    config = voice_llm._authenticate_channel(
        FakeChannel(),
        "Bearer secret-voice-key",
    )

    assert config["llm_api_key"] == "secret-voice-key"


def test_voice_llm_authentication_rejects_wrong_bearer(monkeypatch):
    monkeypatch.setattr(
        voice_llm,
        "reveal_config",
        lambda value: value,
    )

    with pytest.raises(HTTPException) as exc:
        voice_llm._authenticate_channel(
            FakeChannel(),
            "Bearer wrong-key",
        )

    assert exc.value.status_code == 401


def test_resolve_call_id_prefers_xvond_header():
    payload = voice_llm.VoiceChatCompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        call_id="body-call",
    )

    call_id = voice_llm._resolve_call_id(
        payload,
        x_call_id="generic-call",
        x_vapi_call_id="vapi-call",
        x_xvond_call_id="trusted-call",
    )

    assert call_id == "trusted-call"


def test_non_streaming_completion_is_openai_compatible():
    payload = voice_llm._completion_payload(
        request_id="chatcmpl-test",
        model="xvond-agent",
        text="مرحبا",
    )

    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["content"] == "مرحبا"
    assert payload["choices"][0]["finish_reason"] == "stop"


def test_streaming_completion_finishes_with_done():
    chunks = list(
        voice_llm._stream_completion(
            request_id="chatcmpl-test",
            model="xvond-agent",
            text="مرحبا بك",
        )
    )

    assert chunks[0].startswith("data: ")
    assert any("مرحبا بك" in item for item in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"
