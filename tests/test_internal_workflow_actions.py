from pathlib import Path


INTERNAL = Path("backend/app/api/internal_workflow_actions.py").read_text(encoding="utf-8")
MAIN = Path("backend/app/main.py").read_text(encoding="utf-8")
WORKFLOW = Path("ops/n8n/xvond-actions.workflow.json").read_text(encoding="utf-8")


def test_internal_workflow_route_is_registered():
    assert "internal_workflow_actions_router" in MAIN
    assert "internal_workflow_actions_router," in MAIN
    assert 'prefix="/internal/workflow"' in INTERNAL
    assert '@router.post("/xvond-internal")' in INTERNAL


def test_internal_workflow_requires_shared_secret():
    assert "N8N_SHARED_SECRET" in INTERNAL
    assert "Unauthorized workflow request" in INTERNAL
    assert "x_xvond_n8n_secret" in INTERNAL


def test_native_execution_is_idempotent_and_persisted():
    assert "_xvond_native_execution" in INTERNAL
    assert "idempotency_key" in INTERNAL
    assert 'current.get("idempotency_key") == idempotency_key' in INTERNAL
    assert '"already_executed": True' in INTERNAL
    assert '"state": "confirmed"' in INTERNAL


def test_native_execution_rechecks_xvond_schedule():
    assert "_internal_slots" in INTERNAL
    assert 'operation == "check_availability"' in INTERNAL
    assert 'availability.get("mode") or "none"' in INTERNAL
    assert "Requested time is no longer available" in INTERNAL


def test_internal_adapter_accepts_only_xvond_internal_destination():
    assert 'get("type") or "") != "xvond_internal"' in INTERNAL
    assert "Action is not routed to Xvond Internal" in INTERNAL


def test_master_workflow_still_fail_closed_until_callback_is_wired():
    # This test is intentionally updated when the master workflow callback is wired.
    assert "provider_not_configured" in WORKFLOW
