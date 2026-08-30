# Backend Contract

Recommended backend: Python 3.12+ with FastAPI.

## Base URL
`VITE_API_BASE_URL` or equivalent frontend configuration.

## Endpoints

### GET /v1/problems
Returns benchmark problem summaries.

### GET /v1/problems/{slug}
Returns one problem, current default requirements, methods, and latest publishable results.

### POST /v1/problems/{slug}/recommend
Request:
```json
{
  "requirements": {
    "min_accuracy": 95,
    "max_latency_ms": 800,
    "auditability_required": true,
    "monthly_volume": 100000
  }
}
```
Response:
```json
{
  "status": "PASSING_METHOD_FOUND",
  "recommended_method_id": "invoice-rules",
  "reason": "Lowest-complexity method satisfying every hard constraint."
}
```

### POST /v1/runs
Creates a benchmark run. In the portfolio version this should be authenticated/admin-only or disabled publicly until cost controls exist.

### GET /v1/runs/{run_id}
Returns run metadata, status, result metrics, and raw artifact references.

## Frontend-facing problem shape
```json
{
  "slug": "spam-detection",
  "title": "Spam Detection",
  "category": "Classification",
  "description": "...",
  "decision_question": "...",
  "status": "PARTIAL",
  "default_requirements": {},
  "methods": [
    {
      "method_id": "rules",
      "result": {
        "result_state": "MEASURED",
        "accuracy": 92.0594,
        "leakage_audit": {
          "chance_accuracy": 50.0,
          "majority_baseline_accuracy": 87.5403,
          "contamination_rate": 0.0,
          "term_provenance": { "attested_fraction": 0.9688 }
        }
      }
    },
    {
      "method_id": "frontier-llm",
      "result": { "result_state": "NOT_RUN", "accuracy": 0.0 }
    }
  ]
}
```

## Provenance states

`MEASURED`, `ESTIMATED`, `DEMO`, and `NOT_RUN`. The last means the method is
part of the comparison set but has never been run: its numeric fields are
zeroes and are placeholders, never values. Clients must not render or filter on
them — read literally they describe a method that is instant, free, and
perfectly inaccurate.

`status` on a problem is a separate enum (`MEASURED`/`PARTIAL`/`NOT_RUN`),
because how far a comparison set has got is not the provenance of a figure.

Every `MEASURED` result carries `leakage_audit`: the floors the figure must be
read against. A client showing an accuracy without them invites the reader to
treat any number as good news.

## Important rule
Recommendation logic should live in a backend domain module and be mirrored in frontend only for instant demo interaction. Backend remains authoritative once connected.
