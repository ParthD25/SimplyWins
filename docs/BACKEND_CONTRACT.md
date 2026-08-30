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
  "slug": "invoice-field-extraction",
  "title": "Invoice Field Extraction",
  "category": "Document Processing",
  "description": "...",
  "decision_question": "...",
  "status": "DEMO",
  "default_requirements": {},
  "results": []
}
```

## Important rule
Recommendation logic should live in a backend domain module and be mirrored in frontend only for instant demo interaction. Backend remains authoritative once connected.
