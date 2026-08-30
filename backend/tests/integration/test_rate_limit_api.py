"""The limiter as the service actually applies it."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> Iterator[TestClient]:
    monkeypatch.setenv("SIMPLESTWINS_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path}/rl.db")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    db.reset_state()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    db.reset_state()
    get_settings.cache_clear()


@pytest.fixture
def throttled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A deliberately tiny allowance: two requests, refilling very slowly."""
    yield from _client(
        tmp_path,
        monkeypatch,
        SIMPLESTWINS_RATE_LIMIT_BURST="2",
        SIMPLESTWINS_RATE_LIMIT_PER_SECOND="0.01",
    )


def test_requests_over_the_limit_are_rejected(throttled: TestClient) -> None:
    assert throttled.get("/v1/problems").status_code == 200
    assert throttled.get("/v1/problems").status_code == 200

    response = throttled.get("/v1/problems")
    assert response.status_code == 429


def test_rejection_uses_the_standard_error_envelope(throttled: TestClient) -> None:
    """Section 6 requires one error shape; a limiter that invents its own would
    break every client's error handling at exactly the moment it fires."""
    for _ in range(3):
        response = throttled.get("/v1/problems")

    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["details"]["retry_after_seconds"] > 0


def test_retry_after_is_a_whole_number_of_seconds(throttled: TestClient) -> None:
    """Rounded up, so a client that obeys it is not sent back early to be
    rejected a second time."""
    for _ in range(3):
        response = throttled.get("/v1/problems")

    retry_after = response.headers["Retry-After"]
    assert retry_after.isdigit()
    assert int(retry_after) >= 1


def test_allowed_responses_advertise_the_remaining_allowance(throttled: TestClient) -> None:
    first = throttled.get("/v1/problems")
    second = throttled.get("/v1/problems")

    assert first.headers["RateLimit-Limit"] == "2"
    assert first.headers["RateLimit-Remaining"] == "1"
    assert second.headers["RateLimit-Remaining"] == "0"


def test_health_is_never_throttled(throttled: TestClient) -> None:
    """An orchestrator polls health continuously. A limiter that can fail those
    probes causes the restart loop it was meant to prevent."""
    for _ in range(20):
        assert throttled.get("/health").status_code == 200


def test_a_throttled_cross_origin_response_still_carries_cors_headers(
    throttled: TestClient,
) -> None:
    """Otherwise the browser reports an opaque network failure and the client
    never sees the 429 it needs to back off from."""
    for _ in range(3):
        response = throttled.get("/v1/problems", headers={"Origin": "http://localhost:8000"})

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"


class TestForwardedForIsNotTrustedByDefault:
    """The security-critical case. If X-Forwarded-For were honoured
    unconditionally, any client could pick a fresh bucket per request by varying
    a header — which does not weaken the limit, it removes it."""

    def test_varying_the_header_does_not_evade_the_limit(self, throttled: TestClient) -> None:
        codes = [
            throttled.get("/v1/problems", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code
            for i in range(6)
        ]
        assert 429 in codes

    def test_it_is_honoured_when_the_deployment_opts_in(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Behind a proxy that overwrites the header, distinct clients must get
        distinct buckets rather than sharing the proxy's."""
        clients = _client(
            tmp_path,
            monkeypatch,
            SIMPLESTWINS_RATE_LIMIT_BURST="1",
            SIMPLESTWINS_RATE_LIMIT_PER_SECOND="0.01",
            SIMPLESTWINS_RATE_LIMIT_TRUST_FORWARDED_FOR="true",
        )
        client = next(clients)

        first = client.get("/v1/problems", headers={"X-Forwarded-For": "10.0.0.1"})
        other = client.get("/v1/problems", headers={"X-Forwarded-For": "10.0.0.2"})
        repeat = client.get("/v1/problems", headers={"X-Forwarded-For": "10.0.0.1"})

        assert first.status_code == 200
        assert other.status_code == 200
        assert repeat.status_code == 429


def test_the_limiter_can_be_switched_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clients = _client(
        tmp_path,
        monkeypatch,
        SIMPLESTWINS_RATE_LIMIT_ENABLED="false",
        SIMPLESTWINS_RATE_LIMIT_BURST="1",
    )
    client = next(clients)

    codes = [client.get("/v1/problems").status_code for _ in range(5)]
    assert codes == [200] * 5
    assert "RateLimit-Limit" not in client.get("/v1/problems").headers
