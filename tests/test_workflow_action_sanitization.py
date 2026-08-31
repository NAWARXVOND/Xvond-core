from backend.app.modules.tools.workflow_action_request import (
    _workflow_payload,
    _workflow_safe_config,
)


def test_workflow_safe_config_removes_nested_secrets():
    raw = {
        "name": "Book appointment",
        "confirmation_required": True,
        "destination": {
            "type": "workflow",
            "integration_id": 12,
            "api_key": "secret-key",
            "headers": {"Authorization": "Bearer secret"},
            "settings": {
                "calendar_id": "primary",
                "access_token": "secret-token",
                "nested": {"client_secret": "secret", "resource": "appointments"},
            },
        },
    }

    cleaned = _workflow_safe_config(raw)

    assert cleaned["name"] == "Book appointment"
    assert cleaned["confirmation_required"] is True
    assert cleaned["destination"]["integration_id"] == 12
    assert cleaned["destination"]["settings"]["calendar_id"] == "primary"
    assert cleaned["destination"]["settings"]["nested"]["resource"] == "appointments"
    serialized = repr(cleaned).lower()
    assert "secret-key" not in serialized
    assert "secret-token" not in serialized
    assert "authorization" not in serialized
    assert "client_secret" not in serialized
    assert "api_key" not in serialized


def test_workflow_payload_preserves_provider_data_and_identity():
    payload = _workflow_payload(
        {
            "success": True,
            "request_id": "req-123",
            "action": "booking.execute",
            "data": {"booking_id": "bk-1", "status": "confirmed"},
            "error": None,
        }
    )

    assert payload["booking_id"] == "bk-1"
    assert payload["status"] == "confirmed"
    assert payload["_workflow"] == {
        "request_id": "req-123",
        "action": "booking.execute",
    }


def test_workflow_payload_handles_non_object_data():
    payload = _workflow_payload(
        {
            "success": False,
            "request_id": "req-err",
            "action": "custom_api.execute",
            "data": None,
            "error": "failed",
        }
    )

    assert payload["result"] is None
    assert payload["_workflow"]["request_id"] == "req-err"
    assert payload["_workflow"]["action"] == "custom_api.execute"
