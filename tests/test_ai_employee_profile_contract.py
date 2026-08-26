from pathlib import Path

from backend.app.api.admin_ai_employee_profile import DEFAULT_CUSTOMER_CONTROLS


PROFILE_API = Path("backend/app/api/admin_ai_employee_profile.py")
READINESS = Path("backend/app/core/readiness.py")


def test_admin_created_ai_employees_default_to_customer_portal_visibility():
    assert DEFAULT_CUSTOMER_CONTROLS["can_view_conversations"] is True
    assert DEFAULT_CUSTOMER_CONTROLS["can_view_usage"] is True
    assert DEFAULT_CUSTOMER_CONTROLS["can_enable_disable"] is True
    assert DEFAULT_CUSTOMER_CONTROLS["can_edit_prompt"] is False
    assert DEFAULT_CUSTOMER_CONTROLS["can_change_provider"] is False
    assert DEFAULT_CUSTOMER_CONTROLS["can_change_model"] is False


def test_profile_api_ensures_agent_config_on_create_and_legacy_access():
    source = PROFILE_API.read_text(encoding="utf-8-sig")
    assert "def _ensure_agent_config" in source
    assert source.count("_ensure_agent_config(db, agent)") >= 3
    assert "controls.update(row.customer_controls or {})" in source


def test_readiness_exposes_canonical_and_legacy_profile_flags():
    source = READINESS.read_text(encoding="utf-8-sig")
    assert '"company_profile_ready": company_profile_ready' in source
    assert '"profile_ready": company_profile_ready' in source
