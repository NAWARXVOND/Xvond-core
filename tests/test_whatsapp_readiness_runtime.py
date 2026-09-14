from backend.app.modules.channels import whatsapp_connection


def _coexistence_config(**overrides):
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


def test_coexistence_without_business_app_echo_is_not_connected(monkeypatch):
    monkeypatch.setattr(
        whatsapp_connection,
        "whatsapp_meta_onboarding_complete",
        lambda _config: True,
    )

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
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._meta_settings",
        lambda: {"app_id": "app-1"},
    )
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._coexistence_subscription_evidence",
        lambda _meta: {"subscribed_webhook_fields": ["messages", "smb_message_echoes"]},
    )
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._graph_url",
        lambda *_args, **_kwargs: "https://graph.facebook.com/test",
    )
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._graph_request",
        lambda *_args, **_kwargs: {
            "data": [{"whatsapp_business_api_data": {"id": "app-1"}}]
        },
    )

    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    state = whatsapp_connection.whatsapp_connection_state(_coexistence_config())

    assert state["connected"] is False
    assert state["connection_status"] == "coexistence_echo_pending"
    assert state["echo_received"] is False


def test_coexistence_with_verified_subscription_and_echo_is_connected(monkeypatch):
    monkeypatch.setattr(
        whatsapp_connection,
        "whatsapp_meta_onboarding_complete",
        lambda _config: True,
    )

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
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._meta_settings",
        lambda: {"app_id": "app-1"},
    )
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._coexistence_subscription_evidence",
        lambda _meta: {"subscribed_webhook_fields": ["messages", "smb_message_echoes"]},
    )
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._graph_url",
        lambda *_args, **_kwargs: "https://graph.facebook.com/test",
    )
    monkeypatch.setattr(
        "backend.app.api.admin_meta_whatsapp._graph_request",
        lambda *_args, **_kwargs: {
            "data": [{"whatsapp_business_api_data": {"id": "app-1"}}]
        },
    )

    whatsapp_connection.clear_whatsapp_connection_probe_cache()
    state = whatsapp_connection.whatsapp_connection_state(
        _coexistence_config(coexistence_echo_received_at="2026-09-15T00:00:00")
    )

    assert state["connected"] is True
    assert state["connection_status"] == "connected"
