from types import SimpleNamespace

from backend.app.core.config.settings import settings
from backend.app.modules.billing import limits as limits_module


def test_development_enforces_token_limits(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    calls = []

    monkeypatch.setattr(
        limits_module.limits_service,
        "apply_ai_quality_limit",
        lambda db, company_id: (None, None, 2),
    )
    monkeypatch.setattr(
        limits_module.service_limits,
        "check",
        lambda db, company_id, service_code, metric, quantity=1: calls.append(
            ("check", company_id, service_code, metric, quantity)
        ),
    )
    monkeypatch.setattr(
        limits_module.service_limits,
        "record",
        lambda db, company_id, service_code, metric, quantity=1, metadata=None: calls.append(
            ("record", company_id, service_code, metric, quantity)
        ),
    )

    limits_module.limits_service.check_token_limit(SimpleNamespace(), 7)

    assert ("check", 7, "ai_agents", "tokens", 0) in calls
    assert ("record", 7, "ai_agents", "requests", 1) in calls


def test_test_environment_bypasses_commercial_token_limits(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")

    def fail(*args, **kwargs):
        raise AssertionError("commercial service limits should be bypassed in APP_ENV=test")

    monkeypatch.setattr(limits_module.service_limits, "check", fail)
    monkeypatch.setattr(limits_module.service_limits, "record", fail)
    limits_module.limits_service.check_token_limit(SimpleNamespace(), 7)
