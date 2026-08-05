from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import Settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: int


class InMemoryRateLimiter:
    """Thread safe sliding window limiter for a single web process."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= limit:
                retry_after = max(1, int(window_seconds - (now - timestamps[0]) + 0.999))
                return RateLimitDecision(False, 0, retry_after)
            timestamps.append(now)
            return RateLimitDecision(True, max(0, limit - len(timestamps)), 0)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply security headers and bounded API request rates."""

    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.settings = settings
        self.limiter = InMemoryRateLimiter()

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _add_security_headers(response: Response, request: Request, production: bool) -> None:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if production and forwarded_proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        is_api = request.url.path.startswith("/api/")
        is_login = request.url.path == "/api/auth/login" and request.method == "POST"
        is_page = (
            request.method == "GET"
            and request.url.path.startswith("/ui/")
            and "/_nicegui/" not in request.url.path
        )
        if self.settings.rate_limit_enabled and (is_api or is_page):
            if is_login:
                group = "login"
                limit = self.settings.rate_limit_login_requests
            elif is_page:
                group = "page"
                limit = self.settings.rate_limit_page_requests
            else:
                group = "api"
                limit = self.settings.rate_limit_requests
            key = f"{self._client_ip(request)}:{group}"
            decision = self.limiter.check(
                key, limit=limit, window_seconds=self.settings.rate_limit_window_seconds
            )
            if not decision.allowed:
                limited_response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(decision.retry_after)},
                )
                self._add_security_headers(limited_response, request, self.settings.is_production)
                return limited_response

        response = await call_next(request)
        self._add_security_headers(response, request, self.settings.is_production)
        return response
