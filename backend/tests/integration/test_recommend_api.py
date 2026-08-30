"""Contract and behaviour tests for POST /v1/problems/{slug}/recommend.

Constraint logic itself is tested against the pure function in
``tests/unit/test_recommendation.py``, where a method with any combination of
properties can be constructed. These tests cover what the API adds: the
envelope, and the evidence rule applied end to end to the real seeded data.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

SLUGS = ["support-request-routing", "spam-detection", "sentiment-classification"]


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
    body = post_recommend(client, "support-request-routing")

    assert {"status", "recommended_method_id", "reason"} <= set(body)
    assert set(body) == {
        "status",
        "recommended_method_id",
        "reason",
        "passing_method_ids",
        "evaluations",
        "benchmark_definition_version",
        "data_state_notice",
        "measured_count",
        "method_count",
        "best_measured_method_id",
    }


@pytest.mark.parametrize("slug", SLUGS)
def test_no_problem_names_a_winner_while_any_method_is_unrun(client: TestClient, slug: str) -> None:
    """The evidence rule, end to end. Every problem has two measured methods and
    two that have never run, so none of them may recommend anything — an unrun
    method could displace the current leader."""
    body = post_recommend(client, slug, min_accuracy=1)

    assert body["status"] == "BENCHMARK_INCOMPLETE"
    assert body["recommended_method_id"] is None
    assert body["measured_count"] == 2
    assert body["method_count"] == 4


@pytest.mark.parametrize("slug", SLUGS)
def test_unrun_methods_never_enter_the_passing_set(client: TestClient, slug: str) -> None:
    """A NOT_RUN method carries zeroes. Those must never be read as a perfect
    latency and a free cost, which is exactly what an unguarded filter would do."""
    body = post_recommend(client, slug, min_accuracy=1, max_latency_ms=100_000)

    passing = set(body["passing_method_ids"])
    assert "small-model" not in passing
    assert "frontier-llm" not in passing


def test_only_measured_methods_can_enter_the_passing_set(client: TestClient) -> None:
    body = post_recommend(client, "spam-detection", min_accuracy=50)

    evidence = {e["method_id"] for e in body["evaluations"] if e["counts_as_evidence"]}
    assert evidence == {"rules", "ml"}
    assert set(body["passing_method_ids"]) <= evidence


def test_unrun_methods_are_still_returned_so_the_comparison_set_is_visible(
    client: TestClient,
) -> None:
    """Hiding them would make a two-method benchmark look complete."""
    body = post_recommend(client, "sentiment-classification")
    returned = {e["method_id"] for e in body["evaluations"]}

    assert returned == {"rules", "ml", "small-model", "frontier-llm"}
    unrun = [e for e in body["evaluations"] if e["method_id"] == "frontier-llm"][0]
    assert unrun["counts_as_evidence"] is False


def test_best_measured_is_reported_but_is_not_a_recommendation(
    client: TestClient,
) -> None:
    """ "Best" means the simplest measured method that clears the bar, not the
    most accurate one — the whole premise of the project. At a 70% bar the
    keyword baseline clears it at 92.06%, so it leads despite ML scoring higher.
    It is still not a recommendation while two methods remain unrun."""
    body = post_recommend(client, "spam-detection", min_accuracy=70)
    assert body["best_measured_method_id"] == "rules"

    # Raise the bar past the baseline and the lead passes to ML.
    stricter = post_recommend(client, "spam-detection", min_accuracy=95)
    assert stricter["best_measured_method_id"] == "ml"

    assert body["recommended_method_id"] is None
    assert stricter["recommended_method_id"] is None


def test_a_requirement_no_measured_method_meets_still_reports_incomplete(
    client: TestClient,
) -> None:
    """Incompleteness dominates: with methods unrun we cannot say nothing passes,
    only that we do not know."""
    body = post_recommend(client, "support-request-routing", min_accuracy=99.9)

    assert body["status"] == "BENCHMARK_INCOMPLETE"
    assert body["passing_method_ids"] == []


def test_every_method_is_reported_with_its_failed_constraints(
    client: TestClient,
) -> None:
    """A reader needs to see why a method was excluded, not just that it was."""
    body = post_recommend(client, "support-request-routing", min_accuracy=95)
    rules = next(e for e in body["evaluations"] if e["method_id"] == "rules")

    failed = {c["constraint"] for c in rules["constraint_checks"] if not c["passed"]}
    assert "min_accuracy" in failed


def test_monthly_volume_scales_the_projected_cost(client: TestClient) -> None:
    # Large enough that neither projection rounds away to zero: these methods
    # cost fractions of a cent per thousand items.
    small = post_recommend(client, "spam-detection", monthly_volume=10_000_000)
    large = post_recommend(client, "spam-detection", monthly_volume=100_000_000)

    def cost(body: dict[str, Any]) -> float:
        entry = next(e for e in body["evaluations"] if e["method_id"] == "ml")
        return float(entry["projected_monthly_cost"])

    assert cost(large) == pytest.approx(cost(small) * 10, rel=1e-6)


def test_volume_alone_never_excludes_a_method(client: TestClient) -> None:
    body = post_recommend(client, "spam-detection", monthly_volume=10_000_000)

    for evaluation in body["evaluations"]:
        constraints = {c["constraint"] for c in evaluation["constraint_checks"]}
        assert "monthly_volume" not in constraints


def test_notice_accompanies_every_recommendation(client: TestClient) -> None:
    body = post_recommend(client, "spam-detection")
    assert body["data_state_notice"]


def test_unknown_slug_returns_standard_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/v1/problems/no-such-problem/recommend",
        json={
            "requirements": {
                "min_accuracy": 90,
                "max_latency_ms": 1000,
                "auditability_required": False,
                "monthly_volume": 1000,
            }
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "problem_not_found"


def test_missing_requirements_returns_validation_error_envelope(
    client: TestClient,
) -> None:
    response = client.post("/v1/problems/spam-detection/recommend", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_out_of_range_accuracy_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/problems/spam-detection/recommend",
        json={
            "requirements": {
                "min_accuracy": 150,
                "max_latency_ms": 1000,
                "auditability_required": False,
                "monthly_volume": 1000,
            }
        },
    )
    assert response.status_code == 422


def test_unknown_requirement_field_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/problems/spam-detection/recommend",
        json={
            "requirements": {
                "min_accuracy": 90,
                "max_latency_ms": 1000,
                "auditability_required": False,
                "monthly_volume": 1000,
                "vibes": True,
            }
        },
    )
    assert response.status_code == 422
