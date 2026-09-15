from types import SimpleNamespace

from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import public_config, reveal_config
from backend.app.modules.channels.acceptance import (
    ACCEPTANCE_PROOF_KEY,
    customer_roundtrip_verified,
    mark_customer_roundtrip,
)


def _channel():
    return SimpleNamespace(
        config={"allowed_origins": ["https://example.com"], "widget_key": "public-key"},
        customer_roundtrip_verified_at=None,
        customer_roundtrip_source=None,
    )


def test_runtime_acceptance_is_persisted_and_public_config_hides_proof(monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_ENCRYPTION_KEY", "test-acceptance-key-012345678901234567890123")
    channel = _channel()

    assert mark_customer_roundtrip(channel, source="website_runtime_reply") is True
    assert channel.customer_roundtrip_verified_at is not None
    assert channel.customer_roundtrip_source == "website_runtime_reply"
    assert customer_roundtrip_verified(channel) is True

    plain = reveal_config(channel.config)
    assert ACCEPTANCE_PROOF_KEY in plain
    assert customer_roundtrip_verified(plain) is True
    assert ACCEPTANCE_PROOF_KEY not in public_config(channel.config)


def test_mutable_config_timestamp_cannot_forge_acceptance(monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_ENCRYPTION_KEY", "test-acceptance-key-012345678901234567890123")
    injected = {
        "allowed_origins": ["https://example.com"],
        "customer_roundtrip_verified_at": "2099-01-01T00:00:00Z",
        "customer_roundtrip_source": "admin_config",
    }

    assert customer_roundtrip_verified(injected) is False


def test_tampering_with_config_invalidates_signed_compatibility_proof(monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_ENCRYPTION_KEY", "test-acceptance-key-012345678901234567890123")
    channel = _channel()
    mark_customer_roundtrip(channel, source="voice_runtime_turn")

    plain = reveal_config(channel.config)
    assert customer_roundtrip_verified(plain) is True
    plain["allowed_origins"] = ["https://attacker.example"]

    assert customer_roundtrip_verified(plain) is False


def test_first_acceptance_evidence_is_immutable(monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_ENCRYPTION_KEY", "test-acceptance-key-012345678901234567890123")
    channel = _channel()
    assert mark_customer_roundtrip(channel, source="first") is True
    first_at = channel.customer_roundtrip_verified_at
    first_source = channel.customer_roundtrip_source

    assert mark_customer_roundtrip(channel, source="second") is False
    assert channel.customer_roundtrip_verified_at == first_at
    assert channel.customer_roundtrip_source == first_source
