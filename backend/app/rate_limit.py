"""Request rate limiting for the public read endpoints.

Section 11 of PROJECT_STANDARD.md requires public endpoints to be rate limited.
Until now nothing throttled them, which is why docs/DEPLOYMENT.md said the API
was not ready to be exposed.

Design, and its limits, stated plainly:

* The bucket is a **token bucket held in this process's memory**. It therefore
  limits per replica, not per deployment: two replicas behind a load balancer
  allow twice the configured rate. That is honest protection against a single
  client hammering one instance, and it is not a substitute for a shared limiter
  or an edge/WAF rule. The service runs as one container today
  (``backend/Dockerfile``), so per-process and per-deployment coincide; when
  that stops being true this needs to move to a shared store.
* A token bucket rather than a fixed window, because a fixed window lets a
  client spend its whole allowance at the end of one window and again at the
  start of the next — twice the intended rate across the boundary.
* The clock is ``time.monotonic``. Wall-clock time can jump backwards (NTP
  correction, a DST-naive container) and would hand out free allowance.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.errors import error_response

logger = logging.getLogger(__name__)

# Orchestrators poll health continuously and must never be throttled: a limiter
# that can cause a restart loop is worse than no limiter.
EXEMPT_PATHS = frozenset({"/health"})


RATE_LIMITED_CODE = "rate_limited"


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


@dataclass(slots=True)
class TokenBucketLimiter:
    """Allows ``burst`` requests immediately, then ``rate_per_second`` sustained."""

    burst: int
    rate_per_second: float
    # Buckets are evicted once idle for this long, so the table cannot grow
    # without bound: the keys are client-controlled, and an unbounded dict keyed
    # by client address is itself a denial-of-service vector.
    idle_eviction_seconds: float = 3600.0
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _last_evicted_at: float = 0.0

    def _evict_idle(self, now: float) -> None:
        # Amortised: sweeping on every request would make each request O(clients).
        if now - self._last_evicted_at < self.idle_eviction_seconds:
            return
        cutoff = now - self.idle_eviction_seconds
        for key in [k for k, b in self._buckets.items() if b.updated_at < cutoff]:
            del self._buckets[key]
        self._last_evicted_at = now

    def check(self, key: str, now: float | None = None) -> tuple[bool, int, float]:
        """Consume one token for ``key``.

        Returns ``(allowed, remaining, retry_after_seconds)``. ``retry_after`` is
        0.0 when allowed.
        """
        now = time.monotonic() if now is None else now
        self._evict_idle(now)

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(self.burst), updated_at=now)
            self._buckets[key] = bucket

        elapsed = max(0.0, now - bucket.updated_at)
        bucket.tokens = min(float(self.burst), bucket.tokens + elapsed * self.rate_per_second)
        bucket.updated_at = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, int(bucket.tokens), 0.0

        needed = 1.0 - bucket.tokens
        return False, 0, needed / self.rate_per_second


def client_key(request: Request, trust_forwarded_for: bool) -> str:
    """Identify the caller.

    ``X-Forwarded-For`` is honoured **only** when the deployment declares it is
    behind a proxy that sets it. Trusting it unconditionally would let any
    client pick its own bucket by sending a header, which does not merely weaken
    the limit — it removes it.
    """
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the originating client; the rest are proxies.
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        limiter: TokenBucketLimiter,
        trust_forwarded_for: bool = False,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.limiter = limiter
        self.trust_forwarded_for = trust_forwarded_for

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        key = client_key(request, self.trust_forwarded_for)
        allowed, remaining, retry_after = self.limiter.check(key)

        if not allowed:
            logger.warning("Rate limit exceeded", extra={"client": key, "path": request.url.path})
            # Built here rather than raised: see errors.error_response.
            rejection = error_response(
                RATE_LIMITED_CODE,
                "Too many requests. Slow down and retry shortly.",
                {"retry_after_seconds": round(retry_after, 3)},
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
            # Ceiling, so a client obeying Retry-After is never sent back early
            # to be rejected a second time.
            rejection.headers["Retry-After"] = str(max(1, math.ceil(retry_after)))
            rejection.headers["RateLimit-Limit"] = str(self.limiter.burst)
            rejection.headers["RateLimit-Remaining"] = "0"
            return rejection

        response = await call_next(request)
        response.headers["RateLimit-Limit"] = str(self.limiter.burst)
        response.headers["RateLimit-Remaining"] = str(remaining)
        return response
