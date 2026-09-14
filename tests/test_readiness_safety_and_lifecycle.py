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


def test_coexistence_transport_needs_real_echo_before_customer_ready():
    assert readiness._channel_customer_accepted(
        channel_type="whatsapp",
        channel_config={"coexistence": True},
        connected=True,
        connection={"coexistence_ready": False},
    ) is False
    assert readiness._channel_customer_accepted(
        channel_type="whatsapp",
        channel_config={"coexistence": True},
        connected=True,
        connection={"coexistence_ready": True},
    ) is True


def test_non_coexistence_connected_channel_can_be_customer_accepted():
    assert readiness._channel_customer_accepted(
        channel_type="website",
        channel_config={},
        connected=True,
        connection=None,
    ) is True
    assert readiness._channel_customer_accepted(
        channel_type="whatsapp",
        channel_config={"coexistence": False},
        connected=True,
        connection={"coexistence_ready": False},
    ) is True
    assert readiness._channel_customer_accepted(
        channel_type="whatsapp",
        channel_config={"coexistence": True},
        connected=False,
        connection={"coexistence_ready": True},
    ) is False


def test_ready_for_customer_rejects_enabled_channel_pending_acceptance():
    source = inspect.getsource(readiness.company_readiness)
    assert "unaccepted_enabled_channels" in source
    assert "and not unaccepted_enabled_channels" in source
    assert "human takeover acceptance is pending" in source
