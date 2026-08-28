from pathlib import Path


SOURCE = Path("backend/app/api/website_widget.py")


def test_website_readiness_requires_active_ai_agents_entitlement():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'service_limits.entitlement(db, channel.company_id, "ai_agents")' in source
    assert "An active AI Agents service subscription is required" in source


def test_website_activation_enforces_channel_capacity():
    source = SOURCE.read_text(encoding="utf-8")
    assert "limits_service.check_channel_limit(db, channel.company_id)" in source
    assert "if not channel.enabled:" in source
