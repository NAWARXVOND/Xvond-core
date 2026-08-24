from backend.app.core.rate_limit import InMemoryRateLimiter


def test_rate_limiter_blocks_after_limit():
    limiter = InMemoryRateLimiter()

    assert limiter.allow("client", 2, 60)
    assert limiter.allow("client", 2, 60)
    assert not limiter.allow("client", 2, 60)


def test_rate_limiter_separates_keys():
    limiter = InMemoryRateLimiter()

    assert limiter.allow("one", 1, 60)
    assert limiter.allow("two", 1, 60)
