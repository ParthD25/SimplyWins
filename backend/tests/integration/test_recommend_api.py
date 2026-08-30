"""Contract and behaviour tests for POST /v1/problems/{slug}/recommend."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


def post_recommend(client: TestClient, slug: str, **overrides: Any) -> dict[str, Any]:
    requirements = {
        "min_accuracy": 90,
        "max_latency_ms": 1000,
        "auditability_required": False,
        "monthly_volume": 100_000,
    }
    requirements.update(overrides)
    response = client.post(f"/v1/problems/{slug}/recommend", json={"requirements": requirements})
    assert response.status_code == 200, response.text
    return response.json()


def test_response_matches_documented_shape(client: TestClient) -> None:
    body = post_recommend(client, "support-ticket-routing")

    # The contract's three documented fields must be present and named exactly.
    assert {"status", "recommended_method_id", "reason"} <= set(body)
    assert set(body) == {
        "status",
        "recommended_method_id",
        "reason",
        "passing_method_ids",
        "evaluations",
        "benchmark_definition_version",
        "data_state_notice",
    }


def test_default_requirements_reproduce_the_documented_winner(client: TestClient) -> None:
    """The seeded defaults must still select the method the problem describes."""
    detail = client.get("/v1/problems/support-ticket-routing").json()
    body = post_recommend(client, "support-ticket-routing", **detail["default_requirements"])

    assert body["status"] == "PASSING_METHOD_FOUND"
    assert body["recommended_method_id"] == "ticket-ml"


def test_relaxing_accuracy_promotes_the_simpler_rules_method(client: TestClient) -> None:
    body = post_recommend(
        client,
        "support-ticket-routing",
        min_accuracy=91,
        max_latency_ms=500,
        auditability_required=True,
    )

    assert body["recommended_method_id"] == "ticket-rules"


def test_auditability_requirement_excludes_non_auditable_methods(client: TestClient) -> None:
    audited = post_recommend(
        client, "sentiment-classification", min_accuracy=90, auditability_required=True
    )
    unaudited = post_recommend(
        client, "sentiment-classification", min_accuracy=90, auditability_required=False
    )

    # Only the small model and frontier LLM clear 90% here, and neither is
    # auditable, so requiring auditability leaves nothing.
    assert audited["status"] == "NO_PASSING_METHOD"
    assert audited["recommended_method_id"] is None
    assert unaudited["recommended_method_id"] == "sentiment-small"


def test_latency_ceiling_excludes_slow_methods(client: TestClient) -> None:
    body = post_recommend(client, "invoice-field-extraction", min_accuracy=95, max_latency_ms=100)

    assert body["status"] == "NO_PASSING_METHOD"
    rules = next(e for e in body["evaluations"] if e["method_id"] == "invoice-rules")
    assert "max_latency_ms" in rules["failed_constraints"]


def test_impossible_requirements_return_no_passing_method(client: TestClient) -> None:
    body = post_recommend(client, "form-validation", min_accuracy=100, max_latency_ms=1)

    assert body["status"] == "NO_PASSING_METHOD"
    assert body["recommended_method_id"] is None
    assert body["passing_method_ids"] == []
    assert all(not evaluation["passed"] for evaluation in body["evaluations"])


def test_every_method_is_reported_with_its_failed_constraints(client: TestClient) -> None:
    body = post_recommend(client, "invoice-field-extraction", min_accuracy=97)

    assert len(body["evaluations"]) == 4
    rules = next(e for e in body["evaluations"] if e["method_id"] == "invoice-rules")
    assert rules["passed"] is False
    assert rules["failed_constraints"] == ["min_accuracy"]


def test_monthly_volume_scales_the_projected_cost(client: TestClient) -> None:
    small = post_recommend(client, "invoice-field-extraction", monthly_volume=1_000)
    large = post_recommend(client, "invoice-field-extraction", monthly_volume=1_000_000)

    def cost(body: dict[str, Any]) -> float:
        return next(
            e["projected_monthly_cost"]
            for e in body["evaluations"]
            if e["method_id"] == "invoice-frontier"
        )

    assert cost(small) == 18.9
    assert cost(large) == 18900.0


def test_volume_alone_never_excludes_a_method(client: TestClient) -> None:
    """Volume drives cost projection only; it is not a hard constraint."""
    body = post_recommend(client, "invoice-field-extraction", monthly_volume=10_000_000)

    assert body["status"] == "PASSING_METHOD_FOUND"


def test_demo_notice_accompanies_every_recommendation(client: TestClient) -> None:
    body = post_recommend(client, "duplicate-record-detection")

    assert "DEMO" in body["data_state_notice"]


def test_unknown_slug_returns_standard_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/v1/problems/no-such-problem/recommend",
        json={
            "requirements": {
                "min_accuracy": 90,
                "max_latency_ms": 500,
                "auditability_required": False,
                "monthly_volume": 1000,
            }
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "problem_not_found"


def test_missing_requirements_returns_validation_error_envelope(client: TestClient) -> None:
    response = client.post("/v1/problems/form-validation/recommend", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "errors" in body["error"]["details"]


def test_out_of_range_accuracy_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/problems/form-validation/recommend",
        json={
            "requirements": {
                "min_accuracy": 150,
                "max_latency_ms": 500,
                "auditability_required": False,
                "monthly_volume": 1000,
            }
        },
    )

    assert response.status_code == 422


def test_unknown_requirement_field_is_rejected(client: TestClient) -> None:
    """extra="forbid" keeps a typo'd requirement from being silently ignored."""
    response = client.post(
        "/v1/problems/form-validation/recommend",
        json={
            "requirements": {
                "min_accuracy": 90,
                "max_latency_ms": 500,
                "auditability_required": False,
                "monthly_volume": 1000,
                "min_acuracy": 99,
            }
        },
    )

    assert response.status_code == 422


# Verified against the frontend prototype's own recommendation logic. If a
# seeded figure changes, this is the test that should fail first.
DEFAULT_WINNERS = {
    "invoice-field-extraction": "invoice-rules",
    "messy-receipt-extraction": "receipt-small",
    "support-ticket-routing": "ticket-ml",
    "duplicate-record-detection": "dupe-rules",
    "form-validation": "form-rules",
    "sentiment-classification": "sentiment-small",
}


@pytest.mark.parametrize(("slug", "expected"), sorted(DEFAULT_WINNERS.items()))
def test_default_requirements_select_the_expected_method(
    client: TestClient, slug: str, expected: str
) -> None:
    detail = client.get(f"/v1/problems/{slug}").json()
    body = post_recommend(client, slug, **detail["default_requirements"])

    assert body["status"] == "PASSING_METHOD_FOUND"
    assert body["recommended_method_id"] == expected
