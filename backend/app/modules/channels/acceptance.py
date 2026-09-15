from __future__ import annotations

from datetime import UTC, datetime


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def customer_roundtrip_verified(channel) -> bool:
    """Return whether runtime has persisted real customer-path evidence."""

    return getattr(channel, "customer_roundtrip_verified_at", None) is not None


def mark_customer_roundtrip(channel, *, source: str) -> bool:
    """Persist the first successful real-channel round-trip as acceptance evidence.

    Evidence is stored in dedicated AgentChannel columns, never in mutable channel
    config. The first proof is intentionally immutable so later traffic cannot
    rewrite when the customer path was originally accepted.
    """

    if customer_roundtrip_verified(channel):
        return False

    channel.customer_roundtrip_verified_at = _utcnow_naive()
    channel.customer_roundtrip_source = str(source or "runtime")[:100]
    return True
