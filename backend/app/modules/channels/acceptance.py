from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from backend.app.core.config.settings import settings
from backend.app.core.config_secrets import merge_config, reveal_config


ACCEPTANCE_PROOF_KEY = "_xvond_acceptance"


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _signing_secret() -> bytes:
    value = str(settings.CONFIG_ENCRYPTION_KEY or settings.JWT_SECRET or "")
    if not value:
        raise RuntimeError("Channel acceptance signing secret is not configured")
    return value.encode("utf-8")


def _config_digest(config: dict | None) -> str:
    plain = dict(config or {})
    plain.pop(ACCEPTANCE_PROOF_KEY, None)
    payload = json.dumps(
        plain,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _proof_signature(*, verified_at: str, source: str, config_digest: str) -> str:
    payload = f"{verified_at}|{source}|{config_digest}".encode("utf-8")
    return hmac.new(_signing_secret(), payload, hashlib.sha256).hexdigest()


def _valid_compatibility_proof(config: dict | None) -> bool:
    plain = dict(config or {})
    proof = plain.get(ACCEPTANCE_PROOF_KEY)
    if not isinstance(proof, dict):
        return False
    verified_at = str(proof.get("verified_at") or "").strip()
    source = str(proof.get("source") or "").strip()
    signature = str(proof.get("signature") or "").strip()
    if not verified_at or not source or not signature:
        return False
    digest = _config_digest(plain)
    expected = _proof_signature(
        verified_at=verified_at,
        source=source,
        config_digest=digest,
    )
    return hmac.compare_digest(signature, expected)


def customer_roundtrip_verified(subject) -> bool:
    """Return whether runtime persisted authentic real-customer-path evidence.

    New code should pass an ``AgentChannel`` and uses the system-owned database
    timestamp. ``company_readiness`` still passes revealed config during this
    rollout, so a signed internal compatibility proof is accepted there. A raw
    timestamp injected through a config API is never sufficient.
    """

    if hasattr(subject, "customer_roundtrip_verified_at"):
        return getattr(subject, "customer_roundtrip_verified_at", None) is not None
    if isinstance(subject, dict):
        return _valid_compatibility_proof(subject)
    return False


def mark_customer_roundtrip(channel, *, source: str) -> bool:
    """Persist the first successful real-channel round-trip.

    The authoritative proof is stored in dedicated ``AgentChannel`` columns.
    A signed, non-public config mirror keeps the current readiness reader
    backward-compatible until that reader is migrated to the dedicated columns.
    """

    if customer_roundtrip_verified(channel):
        return False

    verified_at = _utcnow_naive()
    source_value = str(source or "runtime")[:100]
    channel.customer_roundtrip_verified_at = verified_at
    channel.customer_roundtrip_source = source_value

    plain = reveal_config(channel.config) or {}
    digest = _config_digest(plain)
    proof = {
        "verified_at": verified_at.replace(tzinfo=UTC).isoformat(),
        "source": source_value,
    }
    proof["signature"] = _proof_signature(
        verified_at=proof["verified_at"],
        source=source_value,
        config_digest=digest,
    )
    channel.config = merge_config(channel.config, {ACCEPTANCE_PROOF_KEY: proof})
    return True
