import json

import pytest
from fastapi import HTTPException

from backend.app.api import admin_voice
from backend.app.modules.channels import vapi_api


def test_public_base_url_requires_https(monkeypatch):
    monkeypatch.setenv("XVOND_PUBLIC_BASE_URL", "http://example.com")

    with pytest.raises(HTTPException) as exc:
        admin_voice._public_base_url()

    assert exc.value.status_code == 503


def test_public_base_url_normalizes_trailing_slash(monkeypatch):
    monkeypatch.setenv("XVOND_PUBLIC_BASE_URL", "https://voice.example.com/")

    assert admin_voice._public_base_url() == "https://voice.example.com"


def test_vapi_request_uses_private_bearer_key(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"id": "assistant-1"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers.get("Authorization")
        captured["method"] = request.get_method()
        captured["body"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("VAPI_API_KEY", "private-vapi-key")
    monkeypatch.setattr(vapi_api.urllib.request, "urlopen", fake_urlopen)

    result = vapi_api.vapi_request(
        "POST",
        "/assistant",
        {"name": "Test Voice"},
    )

    assert result["id"] == "assistant-1"
    assert captured["url"] == "https://api.vapi.ai/assistant"
    assert captured["authorization"] == "Bearer private-vapi-key"
    assert captured["method"] == "POST"
    assert json.loads(captured["body"].decode("utf-8"))["name"] == "Test Voice"


def test_custom_llm_credential_payload(monkeypatch):
    captured = {}

    def fake_request(method, path, payload=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"id": "credential-1"}

    monkeypatch.setattr(vapi_api, "vapi_request", fake_request)

    result = vapi_api.create_custom_llm_credential("xvond-secret")

    assert result["id"] == "credential-1"
    assert captured == {
        "method": "POST",
        "path": "/credential",
        "payload": {
            "provider": "custom-llm",
            "apiKey": "xvond-secret",
        },
    }


def test_attach_assistant_to_existing_phone(monkeypatch):
    captured = {}

    def fake_request(method, path, payload=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"id": "phone-1", "assistantId": "assistant-1"}

    monkeypatch.setattr(vapi_api, "vapi_request", fake_request)

    result = vapi_api.attach_assistant_to_phone("phone-1", "assistant-1")

    assert result["assistantId"] == "assistant-1"
    assert captured == {
        "method": "PATCH",
        "path": "/phone-number/phone-1",
        "payload": {"assistantId": "assistant-1"},
    }
