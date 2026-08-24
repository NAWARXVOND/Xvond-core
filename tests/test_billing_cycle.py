from datetime import datetime

from backend.app.modules.billing.cycle import current_billing_cycle


def test_month_end_billing_cycle_is_stable():
    started = datetime(2026, 1, 31, 10, 0, 0)
    start, end = current_billing_cycle(
        started,
        now=datetime(2026, 3, 1, 9, 0, 0),
    )

    assert start == datetime(2026, 2, 28, 10, 0, 0)
    assert end == datetime(2026, 3, 28, 10, 0, 0)
