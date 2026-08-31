import json
from pathlib import Path


ACTIONS = json.loads(Path("ops/n8n/action-contracts.json").read_text(encoding="utf-8"))
BOOKING = json.loads(Path("ops/n8n/booking-adapter.contract.json").read_text(encoding="utf-8"))
IDEMPOTENCY_SQL = Path("ops/n8n/idempotency.sql").read_text(encoding="utf-8")


def test_booking_adapter_matches_canonical_action_catalog():
    canonical = ACTIONS["actions"]
    for action in ("booking.check_availability", "booking.execute", "booking.cancel"):
        assert action in canonical
        assert action in BOOKING["operations"]
        assert canonical[action]["adapter"] == "booking"
        assert canonical[action]["side_effect"] == BOOKING["operations"][action]["side_effect"]


def test_booking_side_effects_require_safe_idempotency_reconciliation():
    for action in ("booking.execute", "booking.cancel"):
        operation = BOOKING["operations"][action]
        rules = operation["idempotency"]
        assert operation["side_effect"] is True
        assert rules["claim_before_provider_call"] is True
        assert rules["completed_returns_stored_result"] is True
        assert rules["processing_requires_reconciliation"] is True
        assert rules["ambiguous_requires_reconciliation"] is True


def test_workflow_idempotency_store_is_separate_and_fail_safe():
    sql = IDEMPOTENCY_SQL.lower()
    assert "xvond_workflow_idempotency" in sql
    assert "primary key" in sql
    assert "processing" in sql
    assert "completed" in sql
    assert "ambiguous" in sql
    assert "on conflict do nothing" in sql
    assert "do not blindly repeat the side effect" in sql


def test_booking_provider_boundary_stays_outside_xvond_core():
    rules = BOOKING["provider_rules"]
    assert rules["credentials_live_in_workflow_engine"] is True
    assert rules["provider_success_required_for_success_true"] is True
    assert rules["provider_reference_should_be_persisted"] is True
    assert rules["xvond_database_access_forbidden"] is True
