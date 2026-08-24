import calendar
from datetime import datetime


def _add_month(
    value: datetime,
) -> datetime:

    if value.month == 12:
        year = value.year + 1
        month = 1
    else:
        year = value.year
        month = value.month + 1

    day = min(
        value.day,
        calendar.monthrange(
            year,
            month,
        )[1],
    )

    return value.replace(
        year=year,
        month=month,
        day=day,
    )


def current_billing_cycle(
    started_at: datetime,
    now: datetime | None = None,
) -> tuple[
    datetime,
    datetime,
]:

    now = now or datetime.utcnow()

    start = started_at
    end = _add_month(start)

    while end <= now:
        start = end
        end = _add_month(start)

    return start, end
