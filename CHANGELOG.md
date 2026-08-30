# Changelog

## 0.5.0 — Frontend talks to the backend, and migrations
- **Phase 5: the frontend now consumes `/v1`.** `frontend/assets/api.js` loads
  problems from the API when one is configured and reachable; the backend is
  authoritative because it owns the seed and the decision rule.
- **The fallback is announced, never silent.** With no backend configured, or
  one that is unreachable, the page renders the bundled `data.js` and says so
  in a visible note — distinguishing "static preview" from "backend
  unreachable". A visitor is never shown bundled numbers as though the service
  had served them.
- `/v1/problems` summaries now carry `measured_count` and `method_count`, so a
  listing shows evidence progress without fetching every problem in full. That
  took the benchmark page from seven requests to two.
- Added Alembic, wired to the same `SIMPLESTWINS_DATABASE_URL` the app uses so
  a migration cannot run against a different database than the service. Batch
  mode is on, since SQLite cannot `ALTER` most columns.
- Four migration tests: migrations apply, reverse, pass `alembic check`, and
  produce a schema identical to `create_all`. CI runs the drift check, so a
  model change without a migration fails there rather than surfacing in
  production as a missing column.
- 135 tests pass.

## 0.5.0 — Measured results reach the API, and CI
- Added `app/seed/promote.py`: measured results reach the served seed by a
  reproducible command rather than hand-edited JSON. `support-ticket-routing`
  is now **2 of 4 methods measured**, each citing its run id, dataset checksum,
  raw artifact, and sample count.
- **The measured methods do not clear the problem's own requirement.** Its
  default bar is 92% accuracy; measured, rules reach 75.69% and traditional ML
  89.50%. The demo figures claimed 91.7% and 94.6%, i.e. that both passed. The
  API now correctly reports an empty passing set for the measured methods, and
  the evidence rule keeps the illustrative ones out of it.
- `latency_p50_ms` widened from `int` to `float`. The measured methods run in
  fractions of a millisecond, and integer milliseconds displayed a real 0.11ms
  as "0ms" — the type was destroying a real measurement.
- Frontend formatters render sub-millisecond latency and sub-cent cost honestly
  instead of rounding them to zero.
- `Result` carries `cost_state`, `run_id`, and `sample_count`, so a MEASURED
  figure can be traced to the run that produced it. Tests assert that a
  MEASURED result cites its provenance and that a DEMO result does not pretend
  to.
- Added GitHub Actions CI: backend lint, format, strict types, 130 tests, and a
  benchmark smoke run; frontend syntax plus `ci/render-check.mjs`, which renders
  five pages at two widths and verifies the evidence rule in a real browser
  against the module the site ships.

## 0.4.0 — The evidence rule
- Added section 3.1 to `PROJECT_STANDARD.md`: **no value may influence a
  SimplestWins recommendation unless its provenance state is `MEASURED`, and a
  benchmark whose method set mixes states cannot produce a final
  recommendation.** This is now the load-bearing rule of the product.
- `recommend()` enforces it. `DEMO` and `ESTIMATED` methods are still evaluated
  and returned so the UI can show the intended comparison set, but they cannot
  enter the passing set, the ranking, a tie-break, or the Pareto frontier.
- New status `BENCHMARK_INCOMPLETE`, returned while any method is unmeasured.
  It reports how much evidence exists ("2 of 4 methods measured") and names no
  winner, because an unmeasured method could still change the outcome.
- `best_measured_method_id` reports the provisional leader among measured
  methods. It is deliberately not a recommendation and is labelled as such
  everywhere it appears.
- `MethodCandidate.result_state` defaults to `DEMO`, so the rule fails closed:
  a caller who omits provenance gets no recommendation rather than an
  accidental one.
- `/v1` recommendation responses now carry `result_state` and
  `counts_as_evidence` per method, plus `measured_count`, `method_count`, and
  `best_measured_method_id`.
- Frontend mirrors the rule exactly, verified against the shipped module.
  Illustrative rows are muted with a dashed leading edge and an "Illustrative"
  tag; chart points for them are hollow and dashed; the legend names their
  state; an amber banner states the incompleteness above the evidence.
- The rail panel was renamed from "Current Picks" to "Other benchmarks" — with
  nothing measured it contained no picks.
- Because every seeded figure is `DEMO`, the API and UI now correctly decline to
  recommend anything for all six problems. That is the intended behaviour, not
  a regression: the product would rather say "not enough evidence yet" than
  force an answer.
- 124 tests pass, including eleven that exist specifically to stop this rule
  being weakened later.

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
