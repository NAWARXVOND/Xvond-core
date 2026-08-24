from redis.exceptions import RedisError

from backend.app.core.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
)


def test_rate_limiter_blocks_after_limit():
    limiter = InMemoryRateLimiter()

    assert limiter.allow("client", 2, 60)
    assert limiter.allow("client", 2, 60)
    assert not limiter.allow("client", 2, 60)


def test_rate_limiter_separates_keys():
    limiter = InMemoryRateLimiter()

    assert limiter.allow("one", 1, 60)
    assert limiter.allow("two", 1, 60)


class FakeRedis:
    def __init__(self):
        self.values = {}

    def eval(self, script, keys_count, key, window):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]


class BrokenRedis:
    def eval(self, *args):
        raise RedisError("unavailable")


def test_redis_rate_limiter_is_shared_and_atomic():
    client = FakeRedis()
    first = RedisRateLimiter(client)
    second = RedisRateLimiter(client)

    assert first.allow("client", 2, 60)
    assert second.allow("client", 2, 60)
    assert not first.allow("client", 2, 60)


def test_redis_failure_falls_back_only_when_configured():
    fallback = InMemoryRateLimiter()
    development = RedisRateLimiter(BrokenRedis(), fallback=fallback)
    production = RedisRateLimiter(BrokenRedis(), fallback=None)

    assert development.allow("client", 1, 60)
    assert not production.allow("client", 1, 60)
