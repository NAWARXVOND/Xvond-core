from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """Small single-process limiter for the MVP API.

    Use a shared Redis-backed limiter before running multiple API workers.
    """

    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def allow(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        now = monotonic()
        cutoff = now - window_seconds

        with self._lock:
            events = self._events[key]

            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                return False

            events.append(now)
            return True


rate_limiter = InMemoryRateLimiter()
