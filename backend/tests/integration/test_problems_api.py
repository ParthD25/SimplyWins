"""Contract tests for the problem endpoints.

These assert the response *shape* documented in docs/BACKEND_CONTRACT.md, not
just that a request succeeds.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

EXPECTED_SLUGS = {
    "invoice-field-extraction",
    "messy-receipt-extraction",
    "support-ticket-routing",
    "duplicate-record-detection",
    "form-validation",
    "sentiment-classification",
}


def test_health_reports_seeded_problem_count(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["problems_loaded"] == len(EXPECTED_SLUGS)


def test_list_problems_returns_every_seeded_problem(client: TestClient) -> None:
    response = client.get("/v1/problems")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(EXPECTED_SLUGS)
    assert {problem["slug"] for problem in body["problems"]} == EXPECTED_SLUGS


def test_problem_summary_matches_documented_shape(client: TestClient) -> None:
    body = client.get("/v1/problems").json()
    summary = body["problems"][0]

    assert set(summary) == {
        "slug",
        "title",
        "category",
        "description",
        "decision_question",
        "status",
        "benchmark_definition_version",
        "measured_count",
        "method_count",
    }


def test_listing_carries_evidence_counts(client: TestClient) -> None:
    """So a listing can show how far each benchmark has got without fetching
    every problem in full."""
    body = client.get("/v1/problems").json()
    by_slug = {problem["slug"]: problem for problem in body["problems"]}

    assert by_slug["support-ticket-routing"]["measured_count"] == 2
    assert by_slug["support-ticket-routing"]["method_count"] == 4
    assert by_slug["form-validation"]["measured_count"] == 0
    for problem in body["problems"]:
        assert problem["measured_count"] <= problem["method_count"]


def test_problem_detail_matches_documented_shape(client: TestClient) -> None:
    response = client.get("/v1/problems/support-ticket-routing")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "slug",
        "title",
        "category",
        "description",
        "decision_question",
        "status",
        "benchmark_definition_version",
        "measured_count",
        "method_count",
        "rationale",
        "dataset",
        "default_requirements",
        "methods",
    }
    assert set(body["default_requirements"]) == {
        "min_accuracy",
        "max_latency_ms",
        "auditability_required",
        "monthly_volume",
    }
    assert len(body["methods"]) == 4


def test_problem_detail_keys_are_snake_case(client: TestClient) -> None:
    """Section 6 of the standard: backend payloads use snake_case."""
    body = client.get("/v1/problems/support-ticket-routing").json()

    def assert_snake_case(payload: object) -> None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                assert key == key.lower(), f"{key} is not snake_case"
                assert " " not in key
                assert_snake_case(value)
        elif isinstance(payload, list):
            for item in payload:
                assert_snake_case(item)

    assert_snake_case(body)


def test_methods_are_ordered_by_complexity_rank(client: TestClient) -> None:
    body = client.get("/v1/problems/invoice-field-extraction").json()

    ranks = [method["complexity_rank"] for method in body["methods"]]
    assert ranks == sorted(ranks)
    assert ranks == [1, 2, 3, 4]


def test_every_result_declares_a_state_the_api_can_be_held_to(
    client: TestClient,
) -> None:
    """Whatever a result claims, the API must expose the evidence for it."""
    for slug in EXPECTED_SLUGS:
        body = client.get(f"/v1/problems/{slug}").json()
        for method in body["methods"]:
            result = method["result"]
            assert result["result_state"] in {"DEMO", "MEASURED", "ESTIMATED"}
            if result["result_state"] == "MEASURED":
                assert result["run_id"]
                assert result["raw_artifact_uri"]
                assert result["measured_at"]
            else:
                assert result["raw_artifact_uri"] is None
                assert result["measured_at"] is None


def test_support_ticket_routing_serves_its_measured_results(
    client: TestClient,
) -> None:
    """The two methods that were actually run must reach the API as MEASURED."""
    body = client.get("/v1/problems/support-ticket-routing").json()
    by_id = {method["method_id"]: method for method in body["methods"]}

    assert by_id["ticket-rules"]["result"]["result_state"] == "MEASURED"
    assert by_id["ticket-ml"]["result"]["result_state"] == "MEASURED"
    assert by_id["ticket-small"]["result"]["result_state"] == "DEMO"
    assert by_id["ticket-frontier"]["result"]["result_state"] == "DEMO"
    # The measured figures, not the illustrative ones they replaced.
    assert by_id["ticket-rules"]["result"]["accuracy"] == pytest.approx(75.69, abs=0.01)
    assert by_id["ticket-ml"]["result"]["accuracy"] == pytest.approx(89.5, abs=0.01)
    assert body["dataset"]["sha256"]


def test_unknown_slug_returns_standard_error_envelope(client: TestClient) -> None:
    response = client.get("/v1/problems/no-such-problem")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "problem_not_found"
    assert body["error"]["details"] == {"slug": "no-such-problem"}


def test_malformed_slug_is_rejected_with_the_error_envelope(client: TestClient) -> None:
    response = client.get("/v1/problems/Not_A_Slug")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_openapi_document_is_served(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/v1/problems" in paths
    assert "/v1/problems/{slug}" in paths
    assert "/v1/problems/{slug}/recommend" in paths


def test_reported_api_version_matches_the_package(client: TestClient) -> None:
    """A served version string that drifts from the package is a small lie the
    next person has to debug."""
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    expected = tomllib.load(pyproject.open("rb"))["project"]["version"]

    assert client.get("/health").json()["api_version"] == expected


def test_changelog_documents_the_current_version() -> None:
    """The served version and the package version were already held together by
    a test; the changelog was not, and drifted to 0.6.0 while both of the others
    said 0.5.0. A release note for a version nobody is running is worse than
    none, because it is believed."""
    import re
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    pyproject = root / "backend" / "pyproject.toml"
    expected = tomllib.load(pyproject.open("rb"))["project"]["version"]

    changelog = (root / "CHANGELOG.md").read_text()
    headings = re.findall(r"^## (\d+\.\d+\.\d+)", changelog, re.MULTILINE)

    assert headings, "CHANGELOG.md has no versioned headings"
    assert headings[0] == expected, (
        f"CHANGELOG.md's newest entry is {headings[0]}, but the package is {expected}"
    )
