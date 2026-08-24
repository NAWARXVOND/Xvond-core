from starlette.requests import Request

from backend.app import main


def make_request(headers=None):
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [
            (name.lower().encode(), value.encode())
            for name, value in (headers or {}).items()
        ],
        "client": ("203.0.113.10", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    })


def test_forwarded_ip_is_ignored_by_default(monkeypatch):
    monkeypatch.setattr(main.settings, "TRUST_PROXY_HEADERS", False)

    request = make_request({
        "x-forwarded-for": "198.51.100.25",
        "cf-connecting-ip": "198.51.100.26",
    })

    assert main.request_client_ip(request) == "203.0.113.10"


def test_forwarded_ip_is_used_only_when_proxy_trust_is_enabled(monkeypatch):
    monkeypatch.setattr(main.settings, "TRUST_PROXY_HEADERS", True)

    request = make_request({
        "x-forwarded-for": "198.51.100.25, 10.0.0.2",
    })

    assert main.request_client_ip(request) == "198.51.100.25"


class FakeDatabase:
    def __init__(self, error=None):
        self.error = error
        self.closed = False

    def execute(self, _statement):
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


class FakeRateLimiter:
    def __init__(self, healthy):
        self.healthy = healthy

    def healthcheck(self):
        return self.healthy


def test_readiness_reports_healthy_dependencies(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(main, "SessionLocal", lambda: database)
    monkeypatch.setattr(main, "rate_limiter", FakeRateLimiter(True))

    result = main.health()

    assert result["status"] == "healthy"
    assert result["database"] == "ok"
    assert result["redis"] == "ok"
    assert database.closed is True


def test_readiness_fails_when_database_is_unavailable(monkeypatch):
    database = FakeDatabase(RuntimeError("database unavailable"))
    monkeypatch.setattr(main, "SessionLocal", lambda: database)
    monkeypatch.setattr(main, "rate_limiter", FakeRateLimiter(True))

    result = main.health()

    assert result.status_code == 503
    assert database.closed is True


def test_readiness_fails_when_redis_is_unavailable(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(main, "SessionLocal", lambda: database)
    monkeypatch.setattr(main, "rate_limiter", FakeRateLimiter(False))

    result = main.health()

    assert result.status_code == 503
    assert database.closed is True
