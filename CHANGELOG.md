# Changelog

## 0.3.0 — Benchmark runner and the first measured results (Phase 3, part 1)
- Added the benchmark runner: `BenchmarkMethod` protocol, deterministic scoring,
  and an immutable run record carrying every field section 4 of
  `PROJECT_STANDARD.md` requires. Raw per-example predictions are written before
  aggregation, so a published score can always be recomputed from the artifact.
- Added `support-ticket-routing` as the first real benchmark: a 4,000-example
  synthetic dataset (150 hand-written phrasings, ~40% deliberately hard cases),
  keyword routing rules, and TF-IDF + logistic regression.
- **First measured numbers in the project.** On 1,600 held-out examples:
  rules 75.69% accuracy / ~0.11ms p50; traditional ML 89.50% / ~0.71ms.
  Accuracy and macro F1 are `MEASURED` and reproduce exactly; latency is
  measured but noisy; cost is `ESTIMATED` from latency plus a dated compute
  rate, never claimed as measured.
- The measured result contradicts the demo figures the frontend shows. Demo
  data put rules at 91.7% and ML at 94.6%; measurement puts rules 14 points
  behind ML. The illustrative numbers flattered the rules baseline.
- The dataset split is **template-disjoint**. An earlier random split let a
  character n-gram model score 98.75% by memorising phrasing fingerprints —
  72% of test examples shared their opening words with a training example.
  That measured recall of the generator, not generalisation.
- The template pool was expanded from 12 to 30 phrasings per class after the
  first template-disjoint split left too little shared vocabulary to learn
  from: every configuration scored near the 20% chance baseline.
- The ML configuration was selected on a template-disjoint validation split
  carved from the training data. The evaluation split was never consulted.
- `--publish` promotes a run to `benchmarks/published/`, the only place the
  product may cite from, keeping exploratory runs distinct from results.
- scikit-learn is an optional extra; the API does not import it.
- Documentation: `app/benchmarks/README.md` and a dataset card recording
  provenance, licence, the split policy, and five material limitations.
- 112 tests pass; ruff and strict mypy clean.

Not built: any model-provider call, so no small-model or frontier-LLM result
exists. Measured results are not yet served through `/v1`.

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
