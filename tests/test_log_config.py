import json
import logging

from backend.app.core.log_config import (
    JsonFormatter,
    redact,
    safe_request_id,
    set_request_id,
    reset_request_id,
)


def test_request_id_accepts_safe_value_and_replaces_unsafe_value():
    assert safe_request_id("trace-123") == "trace-123"
    generated = safe_request_id("bad request id\n")
    assert generated != "bad request id\n"
    assert len(generated) == 32


def test_redact_removes_nested_secrets():
    result = redact({
        "authorization": "Bearer secret",
        "nested": {"api_key": "private", "safe": "ok"},
    })
    assert result["authorization"] == "[REDACTED]"
    assert result["nested"]["api_key"] == "[REDACTED]"
    assert result["nested"]["safe"] == "ok"


def test_json_formatter_includes_request_correlation():
    token = set_request_id("request-42")
    try:
        record = logging.LogRecord(
            "xvond.test",
            logging.INFO,
            __file__,
            1,
            "completed",
            (),
            None,
        )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["request_id"] == "request-42"
    assert payload["message"] == "completed"
    assert payload["level"] == "INFO"
