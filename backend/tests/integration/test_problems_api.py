"""Contract tests for the problem endpoints.

These assert the response *shape* documented in docs/BACKEND_CONTRACT.md, not
just that a request succeeds.
"""

from __future__ import annotations

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
    }


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


def test_every_seeded_result_is_labelled_demo(client: TestClient) -> None:
    """Nothing in this phase is measured; the API must say so on every result."""
    for slug in EXPECTED_SLUGS:
        body = client.get(f"/v1/problems/{slug}").json()
        assert body["status"] == "DEMO"
        for method in body["methods"]:
            assert method["result"]["result_state"] == "DEMO"
            assert method["result"]["raw_artifact_uri"] is None
            assert method["result"]["measured_at"] is None


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
