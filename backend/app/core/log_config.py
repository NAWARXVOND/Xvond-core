import json
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4


_REQUEST_ID = ContextVar("request_id", default="-")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "access_token",
    "refresh_token",
}


def safe_request_id(value: str | None) -> str:
    candidate = (value or "").strip()
    if candidate and _SAFE_REQUEST_ID.fullmatch(candidate):
        return candidate
    return uuid4().hex


def set_request_id(value: str):
    return _REQUEST_ID.set(value)


def reset_request_id(token):
    _REQUEST_ID.reset(token)


def redact(value):
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if str(key).lower() in _SENSITIVE_KEYS
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(
                record,
                "request_id",
                _REQUEST_ID.get(),
            ),
        }

        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            redact(payload),
            ensure_ascii=False,
            default=str,
        )


def configure_logging(level: str = "INFO", json_logs: bool = True):
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s "
                "[request_id=%(request_id)s] %(message)s"
            )
        )

    root.handlers.clear()
    root.addHandler(handler)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _REQUEST_ID.get()
        return True
