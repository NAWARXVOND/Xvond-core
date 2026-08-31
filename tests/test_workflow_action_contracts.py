import json
from pathlib import Path


CONTRACT_PATH = Path("ops/n8n/action-contracts.json")


def test_workflow_action_contracts_are_valid():
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    actions = payload["actions"]
    assert "booking.execute" in actions
    assert "send_email.execute" in actions
    assert "crm.upsert_contact" in actions
    assert "pos.create_order" in actions
    assert "custom_api.execute" in actions
    assert "notification.send" in actions

    generic = payload["generic_business_action"]
    assert generic["enabled"] is True
    assert generic["allowed_operations"] == ["check_availability", "execute", "cancel"]
    assert generic["action_type_must_match"] is True
    assert generic["module_required"] is True

    for name, contract in actions.items():
        assert "." in name
        assert isinstance(contract.get("required_data"), list)
        assert isinstance(contract.get("required_detail_fields"), list)
        assert isinstance(contract.get("side_effect"), bool)
        assert contract.get("idempotent") is True


def test_side_effect_contracts_require_idempotency_key():
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    for name, contract in payload["actions"].items():
        if contract["side_effect"]:
            assert "idempotency_key" in contract["required_data"], name
