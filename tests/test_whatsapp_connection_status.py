import io
import json
import urllib.error

import pytest

from backend.app.modules.channels import whatsapp_connection


@pytest.fixture(autouse=True)
def clear_probe_cache():
    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    yield
    whatsapp_connection.clear_whatsapp_connection_probe_cache()


class GraphResponse:
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self.body


def coexistence_config(**overrides):
    config = {
        "connection_method": "meta_embedded_signup_coexistence",
        "coexistence": True,
        "waba_id": "waba-1",
        "phone_number_id": "phone-1",
        "access_token": "secret-token",
        "graph_api_version": "v26.0",
    }
    config.update(overrides)
    return config


def test_manual_credentials_are_never_reported_connected(monkeypatch):
    monkeypatch.setattr(
        whatsapp_connection.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: GraphResponse({"id": "phone-1"}),
    )

    state = whatsapp_connection.whatsapp_connection_state(
        {
            "phone_number_id": "phone-1",
            "access_token": "secret-token",
            "graph_api_version": "v26.0",
        }
    )

    assert state["connected"] is False
    assert state["meta_onboarding_complete"] is False
    assert state["connection_status"] == "configured_only"


def test_coexistence_requires_subscriptions_and_real_echo_beyond_phone_check(monkeypatch):
    calls = []

    def urlopen(request, timeout):
        calls.append((request, timeout))
        return GraphResponse({"id": "phone-1"})

    monkeypatch.setattr(whatsapp_connection.urllib.request, "urlopen", urlopen)

    first = whatsapp_connection.whatsapp_connection_state(coexistence_config())
    second = whatsapp_connection.whatsapp_connection_state(coexistence_config())

    assert first["connected"] is False
    assert first["meta_onboarding_complete"] is True
    assert first["connection_status"] == "coexistence_setup_required"
    assert first["connection_issue"]
    assert second == first
    assert len(calls) >= 1
    assert calls[0][0].get_header("Authorization") == "Bearer secret-token"
    assert calls[0][1] == 5.0


def test_meta_error_190_is_a_safe_invalid_token_status(monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"sensitive detail","code":190}}'),
        )

    monkeypatch.setattr(whatsapp_connection.urllib.request, "urlopen", urlopen)

    state = whatsapp_connection.whatsapp_connection_state(coexistence_config())

    assert state["connected"] is False
    assert state["connection_status"] == "invalid_token"
    assert state["meta_error_code"] == 190
    assert "sensitive detail" not in json.dumps(state)
    assert "secret-token" not in json.dumps(state)


def test_inconsistent_coexistence_marker_cannot_be_connected(monkeypatch):
    monkeypatch.setattr(
        whatsapp_connection.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: GraphResponse({"id": "phone-1"}),
    )

    state = whatsapp_connection.whatsapp_connection_state(
        coexistence_config(coexistence=False)
    )

    assert state["connected"] is False
    assert state["meta_onboarding_complete"] is False
    assert state["connection_status"] == "configured_only"


def test_phone_id_mismatch_is_not_connected(monkeypatch):
    monkeypatch.setattr(
        whatsapp_connection.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: GraphResponse({"id": "another-phone"}),
    )

    state = whatsapp_connection.whatsapp_connection_state(coexistence_config())

    assert state["connected"] is False
    assert state["connection_status"] == "phone_mismatch"

