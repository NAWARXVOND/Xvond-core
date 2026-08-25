from datetime import datetime, timezone

from backend.app.core.agent_runtime import _business_clock_context


def test_business_clock_uses_company_timezone():
    fixed_utc = datetime(2026, 8, 26, 1, 30, 0, tzinfo=timezone.utc)

    context = _business_clock_context("Asia/Muscat", fixed_utc)

    assert "Current business date: 2026-08-26" in context
    assert "Current business time: 2026-08-26T05:30:00+04:00" in context
    assert "Business timezone: Asia/Muscat" in context


def test_business_clock_falls_back_to_utc_for_invalid_timezone():
    fixed_utc = datetime(2026, 8, 26, 1, 30, 0, tzinfo=timezone.utc)

    context = _business_clock_context("Invalid/Timezone", fixed_utc)

    assert "Current business date: 2026-08-26" in context
    assert "Current business time: 2026-08-26T01:30:00+00:00" in context
    assert "Business timezone: UTC" in context


def test_business_clock_requires_future_safe_partial_date_resolution():
    fixed_utc = datetime(2026, 8, 26, 1, 30, 0, tzinfo=timezone.utc)

    context = _business_clock_context("Asia/Muscat", fixed_utc)

    assert "next matching calendar date" in context
    assert "Never silently assign a past year" in context
