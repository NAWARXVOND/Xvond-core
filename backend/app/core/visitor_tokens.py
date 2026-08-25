from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from backend.app.core.config.settings import settings


class VisitorTokenError(ValueError):
    pass


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise VisitorTokenError("Invalid visitor token encoding") from exc


def _sign(payload: str) -> str:
    digest = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def issue_website_visitor_token(
    channel_id: int,
    conversation_id: int,
    *,
    now: int | None = None,
    ttl_seconds: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    ttl = int(ttl_seconds or settings.WEBSITE_VISITOR_TOKEN_TTL_SECONDS)
    payload = {
        "v": 1,
        "channel_id": int(channel_id),
        "conversation_id": int(conversation_id),
        "iat": issued_at,
        "exp": issued_at + max(300, ttl),
    }
    encoded = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{encoded}.{_sign(encoded)}"


def verify_website_visitor_token(
    token: str | None,
    *,
    channel_id: int,
    conversation_id: int,
    now: int | None = None,
) -> dict:
    if not token:
        raise VisitorTokenError("Website visitor token is required")

    parts = str(token).split(".")
    if len(parts) != 2:
        raise VisitorTokenError("Invalid website visitor token")
    encoded, received_signature = parts
    expected_signature = _sign(encoded)
    if not hmac.compare_digest(received_signature, expected_signature):
        raise VisitorTokenError("Invalid website visitor token")

    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except VisitorTokenError:
        raise
    except Exception as exc:
        raise VisitorTokenError("Invalid website visitor token") from exc

    if payload.get("v") != 1:
        raise VisitorTokenError("Unsupported website visitor token")
    if int(payload.get("channel_id") or 0) != int(channel_id):
        raise VisitorTokenError("Website visitor token does not belong to this channel")
    if int(payload.get("conversation_id") or 0) != int(conversation_id):
        raise VisitorTokenError("Website visitor token does not belong to this conversation")

    current = int(time.time() if now is None else now)
    expires_at = int(payload.get("exp") or 0)
    issued_at = int(payload.get("iat") or 0)
    if not issued_at or issued_at > current + 60:
        raise VisitorTokenError("Invalid website visitor token issue time")
    if expires_at <= current:
        raise VisitorTokenError("Website visitor token has expired")

    return payload
