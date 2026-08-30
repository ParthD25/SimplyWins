# Changelog

## 0.2.0 — Backend foundation (Phase 2)
- Added a FastAPI service under `backend/` with `GET /health`, `GET /v1/problems`,
  `GET /v1/problems/{slug}`, and `POST /v1/problems/{slug}/recommend`.
- Implemented the decision rule from `PROJECT_STANDARD.md` section 3 as a pure,
  dependency-free function in `app/domain/recommendation.py`. It returns
  `NO_PASSING_METHOD` with a null recommendation when nothing satisfies every
  hard requirement; no winner is forced.
- Added the full tie-break the standard specifies — complexity rank, then cost,
  then latency — which the frontend prototype's mirrored logic does not
  implement (it stops at cost).
- Migrated the six problem definitions into backend-owned versioned seed files
  at `app/seed/v1/problems.json`, converted to `snake_case` and to the uppercase
  `DEMO` data state. The backend is now the source of truth for definitions;
  `frontend/assets/data.js` remains only so the static prototype works offline.
  The two were verified identical on every shared field, and both engines select
  the same method for all six problems at their default requirements.
- Added SQLAlchemy 2.x models for Problem, DatasetVersion, Method, Result,
  BenchmarkRun, and RequirementProfile per `docs/DATA_MODEL.md`. Persistence is
  reached through a repository protocol; SQLite locally, PostgreSQL by URL.
- Added the standard error envelope as the only error shape the API can emit.
- Added structured JSON logging over the standard library `logging` module.
- Added 63 tests: the decision rule (including every tie-break and the no-pass
  state), API contract shapes, the error envelope, seed integrity, and seeding
  idempotency. Lint (ruff) and strict type checking (mypy) pass.
- Recorded provenance honestly: every seeded result carries `result_state:
  DEMO`, dataset hashes are null rather than invented, and every recommendation
  response repeats that these figures are not measured.

Not built in this phase, by design: the benchmark runner, `/v1/runs`, and any
model-provider integration. Those are Phase 3.

## 0.1.0 — Frontend prototype
- Established SimplestWins project standard.
- Added product, data, API, design, QA, and implementation documentation.
- Built responsive static frontend.
- Added six demo benchmark problems.
- Added interactive requirement controls and deterministic frontend recommendation logic.
- Added cost-vs-accuracy chart with table fallback.
- Added backend workspace scaffold.
