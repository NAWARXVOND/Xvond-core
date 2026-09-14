import inspect

from backend.app.core import readiness


def test_provider_readiness_uses_safe_error_label():
    source = inspect.getsource(readiness._provider_runtime)
    assert "safe_error_label(exc)" in source
    assert "str(exc)" not in source


def test_company_readiness_exposes_lifecycle_and_runtime_separately():
    source = inspect.getsource(readiness.company_readiness)
    assert '"active": company.active' in source
    assert '"lifecycle_status": company.lifecycle_status' in source
    assert '"lifecycle_updated_at": company.lifecycle_updated_at' in source


def test_readiness_language_distinguishes_runtime_from_commercial_state():
    source = inspect.getsource(readiness.company_readiness)
    assert "Company runtime is currently stopped" in source
