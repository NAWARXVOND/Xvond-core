from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


META_CONNECTION_METHODS = frozenset(
    {
        "meta_embedded_signup",
        "meta_embedded_signup_coexistence",
    }
)

_GRAPH_VERSION_PATTERN = re.compile(r"^v\d+\.\d+$")
_PROBE_CACHE_TTL_SECONDS = 60.0
_PROBE_CACHE_MAX_ENTRIES = 1024
_probe_cache: dict[tuple[str, ...], tuple[float, dict]] = {}
_probe_lock = threading.Lock()


def clear_whatsapp_connection_probe_cache() -> None:
    """Clear the short-lived process cache used by status checks and tests."""

    with _probe_lock:
        _probe_cache.clear()


def whatsapp_meta_onboarding_complete(config: dict | None) -> bool:
    """Return whether local data proves that Meta onboarding completed.

    Manual credentials are intentionally not considered a Meta connection. A
    WhatsApp Business App coexistence record must also keep its coexistence
    marker so a partial or legacy update cannot be presented as connected.
    """

    config = config or {}
    method = str(config.get("connection_method") or "").strip()
    if method not in META_CONNECTION_METHODS:
        return False
    if method == "meta_embedded_signup_coexistence" and config.get("coexistence") is not True:
        return False
    required = (
        config.get("waba_id"),
        config.get("phone_number_id"),
        config.get("access_token"),
    )
    return all(str(value or "").strip() for value in required)


def _checked_at() -> str:
    return datetime.now(UTC).isoformat()


def _state(
    *,
    connected: bool,
    registered: bool,
    status: str,
    issue: str | None,
    checked_at: str | None = None,
    meta_error_code: int | None = None,
) -> dict:
    return {
        "connected": connected,
        "meta_onboarding_complete": registered,
        "connection_status": status,
        "connection_issue": issue,
        "connection_checked_at": checked_at,
        "meta_error_code": meta_error_code,
    }


def _cache_key(config: dict, token: str) -> tuple[str, ...]:
    return (
        str(config.get("graph_api_version") or "v26.0").strip(),
        str(config.get("phone_number_id") or "").strip(),
        str(config.get("waba_id") or "").strip(),
        str(config.get("connection_method") or "").strip(),
        str(config.get("coexistence") is True),
        hashlib.sha256(token.encode("utf-8")).hexdigest(),
    )


def _cached(key: tuple[str, ...]) -> dict | None:
    with _probe_lock:
        item = _probe_cache.get(key)
        if item is None:
            return None
        created_at, value = item
        if time.monotonic() - created_at >= _PROBE_CACHE_TTL_SECONDS:
            _probe_cache.pop(key, None)
            return None
        return dict(value)


def _store(key: tuple[str, ...], value: dict) -> dict:
    with _probe_lock:
        now = time.monotonic()
        expired_keys = [
            cached_key
            for cached_key, (created_at, _cached_value) in _probe_cache.items()
            if now - created_at >= _PROBE_CACHE_TTL_SECONDS
        ]
        for expired_key in expired_keys:
            _probe_cache.pop(expired_key, None)

        if key not in _probe_cache and len(_probe_cache) >= _PROBE_CACHE_MAX_ENTRIES:
            oldest_key = min(_probe_cache, key=lambda cached_key: _probe_cache[cached_key][0])
            _probe_cache.pop(oldest_key, None)

        _probe_cache[key] = (now, dict(value))
    return value


def _meta_error_code(body: bytes) -> int | None:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
        value = (payload.get("error") or {}).get("code")
        return int(value) if value is not None else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def whatsapp_connection_state(
    config: dict | None,
    *,
    verify_remote: bool = True,
    timeout_seconds: float = 5.0,
) -> dict:
    """Return a safe, truthful WhatsApp/Meta connection state.

    ``connected`` is true only after Embedded Signup data exists and Meta
    accepts the stored token for the stored phone number. Raw Meta responses
    and credentials are never returned.
    """

    config = config or {}
    registered = whatsapp_meta_onboarding_complete(config)
    phone_number_id = str(config.get("phone_number_id") or "").strip()
    access_token = str(config.get("access_token") or "").strip()
    method = str(config.get("connection_method") or "").strip()

    if not phone_number_id or not access_token:
        status = "incomplete" if method in META_CONNECTION_METHODS else "not_configured"
        return _state(
            connected=False,
            registered=registered,
            status=status,
            issue="WhatsApp credentials are incomplete.",
        )

    if not verify_remote:
        return _state(
            connected=False,
            registered=registered,
            status="check_pending" if registered else "configured_only",
            issue=(
                "Meta connection has not been checked yet."
                if registered
                else "Credentials are saved, but Meta Embedded Signup is not connected."
            ),
        )

    graph_api_version = str(config.get("graph_api_version") or "v26.0").strip()
    if not _GRAPH_VERSION_PATTERN.fullmatch(graph_api_version):
        return _state(
            connected=False,
            registered=registered,
            status="invalid_configuration",
            issue="The configured Meta Graph API version is invalid.",
            checked_at=_checked_at(),
        )

    key = _cache_key(config, access_token)
    cached = _cached(key)
    if cached is not None:
        return cached

    url = (
        "https://graph.facebook.com/"
        + urllib.parse.quote(graph_api_version, safe=".")
        + "/"
        + urllib.parse.quote(phone_number_id, safe="")
        + "?"
        + urllib.parse.urlencode({"fields": "id"})
    )
    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read(65536).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read(65536)
        error_code = _meta_error_code(body)
        invalid_token = error_code == 190 or exc.code == 401
        return _store(
            key,
            _state(
                connected=False,
                registered=registered,
                status="invalid_token" if invalid_token else "meta_rejected",
                issue=(
                    "Meta access token is invalid or expired. Reconnect WhatsApp with Meta."
                    if invalid_token
                    else "Meta rejected the WhatsApp connection check."
                ),
                checked_at=_checked_at(),
                meta_error_code=error_code,
            ),
        )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeError):
        return _store(
            key,
            _state(
                connected=False,
                registered=registered,
                status="check_failed",
                issue="Could not verify the WhatsApp connection with Meta.",
                checked_at=_checked_at(),
            ),
        )

    if not isinstance(payload, dict):
        return _store(
            key,
            _state(
                connected=False,
                registered=registered,
                status="check_failed",
                issue="Could not verify the WhatsApp connection with Meta.",
                checked_at=_checked_at(),
            ),
        )

    if str(payload.get("id") or "").strip() != phone_number_id:
        return _store(
            key,
            _state(
                connected=False,
                registered=registered,
                status="phone_mismatch",
                issue="Meta returned a different WhatsApp phone number.",
                checked_at=_checked_at(),
            ),
        )

    if not registered:
        return _store(
            key,
            _state(
                connected=False,
                registered=False,
                status="configured_only",
                issue="Credentials respond, but Meta Embedded Signup is not connected.",
                checked_at=_checked_at(),
            ),
        )

    return _store(
        key,
        _state(
            connected=True,
            registered=True,
            status="connected",
            issue=None,
            checked_at=_checked_at(),
        ),
    )
