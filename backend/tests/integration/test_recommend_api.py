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
        "measured_count",
        "method_count",
        "best_measured_method_id",
    }


def test_seeded_demo_data_produces_no_recommendation(client: TestClient) -> None:
    """Every seeded result is DEMO, so the evidence rule (section 3.1) forbids
    naming a winner however the requirements are set."""
    detail = client.get("/v1/problems/support-ticket-routing").json()
    body = post_recommend(client, "support-ticket-routing", **detail["default_requirements"])

    assert body["status"] == "BENCHMARK_INCOMPLETE"
    assert body["recommended_method_id"] is None
    assert body["measured_count"] == 0
    assert body["method_count"] == 4
    assert "0 of 4" in body["reason"]


def test_demo_methods_are_returned_but_never_recommended(client: TestClient) -> None:
    """The comparison set is still visible; it simply carries no verdict."""
    body = post_recommend(
        client,
        "support-ticket-routing",
        min_accuracy=91,
        max_latency_ms=500,
        auditability_required=True,
    )

    assert body["recommended_method_id"] is None
    assert len(body["evaluations"]) == 4
    assert all(item["result_state"] == "DEMO" for item in body["evaluations"])
    assert all(item["counts_as_evidence"] is False for item in body["evaluations"])


def test_passing_set_is_empty_while_all_results_are_demo(client: TestClient) -> None:
    """A DEMO row may satisfy the constraints, but it is not evidence, so it
    cannot enter the passing set or the Pareto frontier."""
    body = post_recommend(client, "support-ticket-routing", min_accuracy=50)

    assert body["passing_method_ids"] == []
    assert body["best_measured_method_id"] is None
    assert any(item["passed"] for item in body["evaluations"]), "rows still evaluate"


def test_auditability_requirement_excludes_non_auditable_methods(client: TestClient) -> None:
    audited = post_recommend(
        client, "sentiment-classification", min_accuracy=90, auditability_required=True
    )
    unaudited = post_recommend(
        client, "sentiment-classification", min_accuracy=90, auditability_required=False
    )

    # Only the small model and frontier LLM clear 90% here, and neither is
    # auditable, so requiring auditability leaves nothing.
    # Both are BENCHMARK_INCOMPLETE now — the seed is entirely DEMO — but the
    # per-method constraint evaluation must still respond to auditability.
    assert audited["recommended_method_id"] is None
    assert unaudited["recommended_method_id"] is None
    audited_small = next(e for e in audited["evaluations"] if e["method_id"] == "sentiment-small")
    unaudited_small = next(
        e for e in unaudited["evaluations"] if e["method_id"] == "sentiment-small"
    )
    assert "auditability_required" in audited_small["failed_constraints"]
    assert unaudited_small["passed"] is True


def test_latency_ceiling_excludes_slow_methods(client: TestClient) -> None:
    body = post_recommend(client, "invoice-field-extraction", min_accuracy=95, max_latency_ms=100)

    assert body["recommended_method_id"] is None
    rules = next(e for e in body["evaluations"] if e["method_id"] == "invoice-rules")
    assert "max_latency_ms" in rules["failed_constraints"]


def test_impossible_requirements_return_no_passing_method(client: TestClient) -> None:
    body = post_recommend(client, "form-validation", min_accuracy=100, max_latency_ms=1)

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

    invoice_rules = next(e for e in body["evaluations"] if e["method_id"] == "invoice-rules")
    assert invoice_rules["passed"] is True


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


# Every seeded method is DEMO, so no problem can name a winner yet. These were
# the expected picks under the old behaviour; they are retained as the shape the
# recommendation should take once the methods are actually measured.
DEFAULT_WINNERS = {
    "invoice-field-extraction": "invoice-rules",
    "messy-receipt-extraction": "receipt-small",
    "support-ticket-routing": "ticket-ml",
    "duplicate-record-detection": "dupe-rules",
    "form-validation": "form-rules",
    "sentiment-classification": "sentiment-small",
}


@pytest.mark.parametrize(("slug", "expected"), sorted(DEFAULT_WINNERS.items()))
def test_no_problem_names_a_winner_while_its_results_are_demo(
    client: TestClient, slug: str, expected: str
) -> None:
    detail = client.get(f"/v1/problems/{slug}").json()
    body = post_recommend(client, slug, **detail["default_requirements"])

    assert body["status"] == "BENCHMARK_INCOMPLETE"
    assert body["recommended_method_id"] is None
    assert body["measured_count"] == 0
    # The method that would win once measured is still visible in the set.
    assert expected in {item["method_id"] for item in body["evaluations"]}
