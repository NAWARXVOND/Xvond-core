from fastapi import HTTPException
import pytest

from backend.app.api import admin_meta_whatsapp as meta_whatsapp


def test_meta_settings_read_environment(monkeypatch):
    monkeypatch.setenv("META_APP_ID", "app-123")
    monkeypatch.setenv("META_APP_SECRET", "secret-123")
    monkeypatch.setenv("META_WHATSAPP_CONFIG_ID", "config-123")
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TOKEN", "verify-123")
    monkeypatch.setenv("META_GRAPH_API_VERSION", "v23.0")

    config = meta_whatsapp._meta_settings()

    assert config["app_id"] == "app-123"
    assert config["app_secret"] == "secret-123"
    assert config["config_id"] == "config-123"
    assert config["verify_token"] == "verify-123"
    assert config["graph_api_version"] == "v23.0"


def test_exchange_code_for_token(monkeypatch):
    captured = {}

    def fake_graph_request(url, access_token=None):
        captured["url"] = url
        captured["access_token"] = access_token
        return {"access_token": "business-token"}

    monkeypatch.setattr(meta_whatsapp, "_graph_request", fake_graph_request)

    token = meta_whatsapp._exchange_code_for_token(
        "one-time-code",
        {
            "app_id": "app-123",
            "app_secret": "secret-123",
            "graph_api_version": "v23.0",
            "redirect_uri": "",
        },
    )

    assert token == "business-token"
    assert "oauth/access_token" in captured["url"]
    assert "client_id=app-123" in captured["url"]
    assert "code=one-time-code" in captured["url"]
    assert captured["access_token"] is None


def test_verify_phone_belongs_to_waba(monkeypatch):
    monkeypatch.setattr(
        meta_whatsapp,
        "_graph_request",
        lambda url, access_token=None: {
            "data": [
                {
                    "id": "phone-456",
                    "display_phone_number": "+96800000000",
                    "verified_name": "Example Business",
                }
            ]
        },
    )

    phone = meta_whatsapp._verify_phone_belongs_to_waba(
        waba_id="waba-123",
        phone_number_id="phone-456",
        access_token="business-token",
        graph_api_version="v23.0",
    )

    assert phone["id"] == "phone-456"
    assert phone["verified_name"] == "Example Business"


def test_verify_phone_rejects_wrong_waba(monkeypatch):
    monkeypatch.setattr(
        meta_whatsapp,
        "_graph_request",
        lambda url, access_token=None: {"data": []},
    )

    with pytest.raises(HTTPException) as exc:
        meta_whatsapp._verify_phone_belongs_to_waba(
            waba_id="waba-123",
            phone_number_id="phone-456",
            access_token="business-token",
            graph_api_version="v23.0",
        )

    assert exc.value.status_code == 400
