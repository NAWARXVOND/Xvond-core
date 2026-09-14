import inspect

from backend.app.api import admin_ai_employee_profile, customer_agents


def test_admin_employee_updates_do_not_write_persona_into_channels():
    source = inspect.getsource(admin_ai_employee_profile.update_profile)
    assert "employee_setup" not in source
    assert "channel.config" not in source
    assert "_upsert_profile" in source
    assert "_set_agent_behavior" in source


def test_customer_employee_updates_do_not_write_persona_into_channels():
    source = inspect.getsource(customer_agents.update_agent)
    assert "employee_setup" not in source
    assert "channel.config" not in source
    assert "_upsert_profile" in source
    assert "_set_agent_behavior" in source


def test_legacy_channel_setup_is_read_only_backfill_compatibility():
    source = inspect.getsource(admin_ai_employee_profile._setup_from_channels)
    doc = (admin_ai_employee_profile._setup_from_channels.__doc__ or "").lower()
    assert 'config.get("employee_setup")' in source
    assert "legacy" in doc
    assert "backfill" in doc
    assert "never receive employee persona/behavior state again" in doc
