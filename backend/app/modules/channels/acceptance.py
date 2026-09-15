from __future__ import annotations

from datetime import UTC, datetime

from backend.app.core.config_secrets import merge_config, reveal_config


CUSTOMER_ROUNDTRIP_KEY = "customer_roundtrip_verified_at"
CUSTOMER_ROUNDTRIP_SOURCE_KEY = "customer_roundtrip_source"


def customer_roundtrip_verified(config: dict | None) -> bool:
    value = (config or {}).get(CUSTOMER_ROUNDTRIP_KEY)
    return bool(str(value or "").strip())


def mark_customer_roundtrip(channel, *, source: str) -> bool:
    """Persist the first successful real-channel round-trip as acceptance evidence.

    The marker lives in AgentChannel.config so readiness can evaluate it without a
    schema migration. Existing encrypted channel secrets are preserved by
    ``merge_config``. The first proof is intentionally immutable; later traffic
    should not erase when the channel was initially accepted.
    """

    config = reveal_config(channel.config) or {}
    if customer_roundtrip_verified(config):
        return False

    channel.config = merge_config(
        channel.config,
        {
            CUSTOMER_ROUNDTRIP_KEY: datetime.now(UTC).isoformat(),
            CUSTOMER_ROUNDTRIP_SOURCE_KEY: str(source or "runtime")[:100],
        },
    )
    return True
