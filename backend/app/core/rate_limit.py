from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config.settings import settings


class InMemoryRateLimiter:
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


class RedisRateLimiter:
    """Atomic shared rate limiter for multi-worker production."""

    _SCRIPT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    return current
    """

    def __init__(self, client: Redis, fallback=None):
        self.client = client
        self.fallback = fallback

    def allow(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        redis_key = f"xvond:rate:{key}"

        try:
            current = int(
                self.client.eval(
                    self._SCRIPT,
                    1,
                    redis_key,
                    window_seconds,
                )
            )
            return current <= limit
        except RedisError:
            if self.fallback is not None:
                return self.fallback.allow(
                    key,
                    limit,
                    window_seconds,
                )

            # Production fails closed when the shared limiter is unavailable.
            return False


def build_rate_limiter():
    memory = InMemoryRateLimiter()

    if not settings.REDIS_URL:
        return memory

    client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )
    return RedisRateLimiter(
        client,
        fallback=None if settings.is_production else memory,
    )


rate_limiter = build_rate_limiter()
