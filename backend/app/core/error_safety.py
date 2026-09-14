from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException


_RETRYABLE_TYPES = (
    TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.NetworkError,
)


def safe_error_type(error: BaseException | None) -> str:
    """Return a bounded class name without persisting exception text.

    Provider SDKs and third-party integrations may include request bodies,
    prompts, credentials, or customer content in exception strings. Xvond's
    durable telemetry must therefore store structural metadata only.
    """
    if error is None:
        return "UnknownError"
    name = type(error).__name__ or "Error"
    return name[:120]


def safe_error_category(error: BaseException | None) -> str:
    if error is None:
        return "unknown"
    if isinstance(error, HTTPException):
        if error.status_code == 429:
            return "rate_limit"
        if 400 <= error.status_code < 500:
            return "request"
        return "upstream"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(error, (ConnectionError, httpx.NetworkError)):
        return "network"
    if isinstance(error, ValueError):
        return "validation"
    return "upstream"


def safe_error_retryable(error: BaseException | None) -> bool:
    if error is None:
        return False
    if isinstance(error, _RETRYABLE_TYPES):
        return True
    if isinstance(error, HTTPException):
        return error.status_code == 429 or error.status_code >= 500
    return False


def safe_error_metadata(error: BaseException | None, *, code: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "error_type": safe_error_type(error),
        "error_category": safe_error_category(error),
        "retryable": safe_error_retryable(error),
    }
    if code:
        result["error_code"] = str(code)[:120]
    return result


def safe_error_label(error: BaseException | None) -> str:
    """Compact durable label suitable for AIUsage.error_message.

    This intentionally contains no exception message text.
    """
    meta = safe_error_metadata(error)
    return f"{meta['error_category']}:{meta['error_type']}"[:255]
