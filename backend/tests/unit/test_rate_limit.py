"""Unit tests for the token bucket itself.

The clock is injected throughout rather than slept on, so these are exact
rather than timing-dependent.
"""

from __future__ import annotations

from app.rate_limit import TokenBucketLimiter


def test_burst_is_allowed_then_exhausted() -> None:
    limiter = TokenBucketLimiter(burst=3, rate_per_second=1.0)

    assert [limiter.check("a", now=0.0)[0] for _ in range(3)] == [True, True, True]

    allowed, remaining, retry_after = limiter.check("a", now=0.0)
    assert allowed is False
    assert remaining == 0
    assert retry_after == 1.0  # one token at one per second


def test_tokens_refill_over_time() -> None:
    limiter = TokenBucketLimiter(burst=2, rate_per_second=2.0)
    limiter.check("a", now=0.0)
    limiter.check("a", now=0.0)
    assert limiter.check("a", now=0.0)[0] is False

    # Half a second at two per second is exactly one token.
    assert limiter.check("a", now=0.5)[0] is True
    assert limiter.check("a", now=0.5)[0] is False


def test_refill_never_exceeds_burst() -> None:
    """An idle client returns to its allowance, not to an accumulated surplus."""
    limiter = TokenBucketLimiter(burst=5, rate_per_second=10.0)
    limiter.check("a", now=0.0)

    # Idle for an hour: at ten per second that would be 36,000 tokens uncapped.
    allowed = [limiter.check("a", now=3600.0)[0] for _ in range(6)]
    assert allowed == [True, True, True, True, True, False]


def test_clients_are_limited_independently() -> None:
    limiter = TokenBucketLimiter(burst=1, rate_per_second=1.0)
    assert limiter.check("a", now=0.0)[0] is True
    assert limiter.check("a", now=0.0)[0] is False
    # b must be unaffected by a exhausting its bucket.
    assert limiter.check("b", now=0.0)[0] is True


def test_a_backwards_clock_grants_no_free_allowance() -> None:
    """Defensive: elapsed time is clamped at zero."""
    limiter = TokenBucketLimiter(burst=1, rate_per_second=1.0)
    assert limiter.check("a", now=100.0)[0] is True
    assert limiter.check("a", now=50.0)[0] is False


def test_idle_buckets_are_evicted() -> None:
    """The keys are client-controlled, so an unbounded table is itself a
    denial-of-service vector."""
    limiter = TokenBucketLimiter(burst=1, rate_per_second=1.0, idle_eviction_seconds=10.0)

    for i in range(50):
        limiter.check(f"client-{i}", now=0.0)
    assert len(limiter._buckets) == 50

    # One request well after the idle window sweeps the rest away.
    limiter.check("late", now=1000.0)
    assert len(limiter._buckets) == 1


def test_active_buckets_survive_eviction() -> None:
    limiter = TokenBucketLimiter(burst=5, rate_per_second=1.0, idle_eviction_seconds=10.0)
    limiter.check("old", now=0.0)
    limiter.check("recent", now=95.0)

    limiter.check("new", now=100.0)

    assert "old" not in limiter._buckets
    assert "recent" in limiter._buckets
