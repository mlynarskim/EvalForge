from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.middleware.security import InMemoryRateLimiter, SecurityMiddleware


def test_sliding_window_blocks_and_recovers() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])

    assert limiter.check("visitor", limit=2, window_seconds=60).allowed is True
    assert limiter.check("visitor", limit=2, window_seconds=60).allowed is True
    blocked = limiter.check("visitor", limit=2, window_seconds=60)
    assert blocked.allowed is False
    assert blocked.retry_after == 60

    now[0] = 161.0
    assert limiter.check("visitor", limit=2, window_seconds=60).allowed is True


def test_middleware_limits_login_and_sets_security_headers() -> None:
    test_settings = Settings(
        app_env="production",
        session_secret="test-session-secret-with-at-least-thirty-two-characters",
        rate_limit_login_requests=2,
        rate_limit_window_seconds=60,
    )
    test_app = FastAPI()
    test_app.add_middleware(SecurityMiddleware, settings=test_settings)

    @test_app.post("/api/auth/login")
    def login() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(test_app)
    headers = {"x-forwarded-for": "203.0.113.10", "x-forwarded-proto": "https"}

    first = client.post("/api/auth/login", headers=headers)
    second = client.post("/api/auth/login", headers=headers)
    blocked = client.post("/api/auth/login", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert blocked.headers["x-content-type-options"] == "nosniff"
    assert blocked.headers["x-frame-options"] == "DENY"
    assert blocked.headers["strict-transport-security"] == "max-age=31536000"
