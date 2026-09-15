from backend.app.modules.channels import whatsapp_connection


class GraphResponse:
    def __init__(self, payload: bytes = b'{"id":"phone-1"}'):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self.payload


def coexistence_config(**overrides):
    config = {
        "connection_method": "meta_embedded_signup_coexistence",
        "coexistence": True,
        "waba_id": "waba-1",
        "phone_number_id": "phone-1",
        "access_token": "secret-token",
        "graph_api_version": "v26.0",
        "waba_subscription_verified": True,
        "subscribed_webhook_fields": ["messages", "smb_message_echoes"],
    }
    config.update(overrides)
    return config


def test_coexistence_setup_uses_persisted_signup_evidence():
    assert whatsapp_connection._coexistence_setup_recorded(coexistence_config()) is True
    assert (
        whatsapp_connection._coexistence_setup_recorded(
            coexistence_config(waba_subscription_verified=False)
        )
        is False
    )
    assert (
        whatsapp_connection._coexistence_setup_recorded(
            coexistence_config(subscribed_webhook_fields=["messages"])
        )
        is False
    )


def test_remote_connection_probe_is_cached_for_at_least_ten_minutes():
    assert whatsapp_connection._PROBE_CACHE_TTL_SECONDS >= 600


def test_coexistence_connection_uses_one_meta_get_then_cache(monkeypatch):
    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    calls = []

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return GraphResponse()

    monkeypatch.setattr(whatsapp_connection.urllib.request, "urlopen", urlopen)

    first = whatsapp_connection.whatsapp_connection_state(coexistence_config())
    second = whatsapp_connection.whatsapp_connection_state(coexistence_config())

    assert first["connected"] is True
    assert first["coexistence_ready"] is False
    assert second == first
    assert len(calls) == 1
    assert "/phone-1?" in calls[0][0]
    assert calls[0][1] == 5.0


def test_missing_persisted_subscription_evidence_blocks_coexistence(monkeypatch):
    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    calls = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        return GraphResponse()

    monkeypatch.setattr(whatsapp_connection.urllib.request, "urlopen", urlopen)

    state = whatsapp_connection.whatsapp_connection_state(
        coexistence_config(subscribed_webhook_fields=["messages"])
    )

    assert state["connected"] is False
    assert state["connection_status"] == "coexistence_setup_required"
    assert len(calls) == 1
