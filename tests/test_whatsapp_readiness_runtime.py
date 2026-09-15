from backend.app.modules.channels import whatsapp_connection


def _coexistence_config(**overrides):
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


def _mock_verified_transport(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit=-1):
            return b'{"id":"phone-1"}'

    monkeypatch.setattr(
        whatsapp_connection.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(),
    )


def test_coexistence_transport_can_reply_before_first_business_app_echo(monkeypatch):
    _mock_verified_transport(monkeypatch)

    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    state = whatsapp_connection.whatsapp_connection_state(_coexistence_config())

    assert state["connected"] is True
    assert state["connection_status"] == "connected"
    assert state["coexistence_ready"] is False
    assert state["echo_received"] is False
    assert "first observed human reply" in state["connection_issue"]


def test_coexistence_with_verified_subscription_and_echo_is_fully_ready(monkeypatch):
    _mock_verified_transport(monkeypatch)

    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    state = whatsapp_connection.whatsapp_connection_state(
        _coexistence_config(coexistence_echo_received_at="2026-09-15T00:00:00")
    )

    assert state["connected"] is True
    assert state["connection_status"] == "connected"
    assert state["coexistence_ready"] is True
    assert state["echo_received"] is True
    assert state["connection_issue"] is None
