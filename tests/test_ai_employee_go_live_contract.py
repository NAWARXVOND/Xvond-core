from pathlib import Path


PROFILE = Path("backend/app/api/admin_ai_employee_profile.py").read_text(encoding="utf-8")
READINESS = Path("backend/app/api/admin_delivery_readiness.py").read_text(encoding="utf-8")
GUIDE = Path("frontend/admin/ai-employee-setup-guide.js").read_text(encoding="utf-8")


def test_new_employee_is_draft_until_explicit_activation():
    assert "enabled=False" in PROFILE
    assert '"lifecycle": "draft"' in PROFILE
    assert "Go Live" in GUIDE


def test_activation_requires_setup_readiness_and_plan_capacity():
    assert 'if not state["payload"]["setup_ready"]' in READINESS
    assert "limits_service.check_agent_limit(db, company_id)" in READINESS
    assert "agent.enabled = True" in READINESS


def test_deactivation_preserves_configuration():
    assert '@router.post("/companies/{company_id}/agents/{agent_id}/deactivate")' in READINESS
    assert "agent.enabled = False" in READINESS
    assert "db.delete(agent)" not in READINESS
