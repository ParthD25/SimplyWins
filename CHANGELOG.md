# Changelog

## 0.8.0 — Real corpora, and the floors beside every number

- **The benchmark could not produce a low score, so it was replaced.** Its
  corpus was generated in this repository and the keyword baseline was written
  by the same author. 73.6% of the baseline's 106 keywords appeared verbatim in
  the generator's own templates; restricted to those it scored 78.9%, identical
  to the full vocabulary, and restricted to the 28 terms the generator never
  used, 25.3% against a 20% floor. **The keywords chosen independently carried
  no signal at all.** The docstring claiming the vocabulary had been picked
  "without consulting the dataset generator's phrasings" was false and is gone.
- **Three real corpora replace it**, each downloaded from a named public source
  with its licence and limitations recorded: CFPB consumer complaints (7-queue
  routing, 3,066 rows), the UCI SMS Spam Collection (5,159 rows), and SST-2
  film review sentences (9,602 rows). Nobody writing a method here chose the
  words in those test sets.
- Measured, with zero train/test overlap on all three:

  | Problem | Rules | TF-IDF + logreg | Chance | Commonest label |
  | --- | ---: | ---: | ---: | ---: |
  | Support request routing | 46.43% | 79.87% | 14.29% | 14.29% |
  | Spam detection | 92.06% | 98.77% | 50.00% | 87.54% |
  | Sentiment | 59.33% | 78.83% | 50.00% | 51.63% |

  The rules baseline now genuinely loses on routing by 33 points, which the
  synthetic version never showed. On spam its whole vocabulary buys four and a
  half points over answering "ham" every time.
- **Every run carries an audit** of whether its result could have come out low:
  the majority-class floor, uniform chance, train/test contamination, and for
  keyword methods the vocabulary split by attestation with both halves scored
  separately. Served through a typed API contract and shown on the benchmark
  page. A test reconstructs the original bug in miniature to prove the audit
  still reports it.
- **Both hosted tiers are implemented** against the Anthropic SDK — a small
  model and a frontier one, sharing prompt and parsing so a difference between
  them is the model rather than the harness. They stay unmeasured until a key
  exists: `setup()` raises rather than estimating. Their cost will be arithmetic
  on the tokens the response reports, the only MEASURED cost in the project. No
  server-side refusal fallback, because silently rerouting to another model
  would put its answers in this model's column.
- **New `NOT_RUN` state**, distinct from `DEMO`: a method with no figures at
  all rather than illustrative ones. Listed rather than hidden, because the
  evidence rule turns on every method having been measured. Three defects came
  from treating such a method as one scoring zero — the chart plotted them at
  the origin, `methodMeetsRequirements` would have passed them as instant and
  free at a low accuracy bar, and the table printed their zeroes as figures.
  All three fixed and guarded; the browser gate asserts the second directly
  against the module, because no slider can reach the bar that exposes it.
- Six problems became three, and the four with no real corpus were removed
  rather than left showing invented numbers. Seed v1 and v2 are deleted; both
  contained only fabricated data and were one environment variable away from
  production.
- `frontend/assets/data.js` is generated from the seed and checked for drift in
  CI. It was maintained by hand, which is how a regex once rewrote a cost into
  `1e-06e-06` and broke the module at parse time.
- Sub-millisecond latency no longer rounds to "0ms", which stated something
  impossible for a method answering in microseconds.
- 176 tests pass.

## 0.7.0 — Rate limiting
- **Every endpoint except `/health` is now rate limited**, closing the last
  requirement in section 11 of `PROJECT_STANDARD.md` that had no
  implementation. A token bucket keyed on the client address: `RateLimit-Limit`
  and `RateLimit-Remaining` on allowed responses, and a `429` carrying the
  standard error envelope plus `Retry-After` in whole seconds, rounded up so a
  client that obeys it is not sent back early to be rejected again.
- **A token bucket rather than a fixed window**, because a fixed window lets a
  client spend its whole allowance at the end of one window and again at the
  start of the next — twice the intended rate across the boundary.
- **`X-Forwarded-For` is not trusted by default.** Honouring it unconditionally
  would let any client pick a fresh bucket per request by varying a header,
  which does not weaken the limit but removes it. It is used only when a
  deployment declares it sits behind a proxy that sets the header. A test
  asserts a varying header cannot evade the limit, and it was confirmed to have
  teeth: forcing the header to always be trusted makes that test fail.
- **`/health` is exempt on purpose.** Orchestrators poll it continuously, and a
  limiter that can fail those probes causes the restart loop it exists to
  prevent.
- The limiter is installed inside CORS so a throttled cross-origin caller still
  receives CORS headers on its 429; without them the browser reports an opaque
  network error and the client never sees the status it needs to back off from.
  Asserted by a test rather than reasoned about.
- Idle buckets are evicted, because the keys are client-controlled and an
  unbounded table keyed by client address is itself a denial-of-service vector.
- The clock is `time.monotonic`; wall-clock time can jump backwards and hand out
  free allowance.
- Stated plainly in `docs/DEPLOYMENT.md`: the bucket lives in process memory, so
  it limits per replica rather than per deployment. One container today, so the
  two coincide — but it is not a substitute for an edge rule.
- `error_response` in `app/errors.py` is now public, because exception handlers
  registered on the app run *inside* the user middleware stack: an `ApiError`
  raised from middleware never reaches them and would surface as a 500. The
  middleware builds the envelope directly, through the one function that
  defines its shape.
- 153 tests pass.

## 0.6.1 — The CI gate actually gates
- **The frontend syntax check was inert.** `node --check <file>` returns 0
  *without parsing* when Node detects a `.js` file as an ES module, and all
  three frontend modules are ESM — the step passed `export const a = = 1`. It
  had never checked anything since being written. Replaced with a real parse via
  `--input-type=module`, which reports against `[stdin]`, so the filename is
  printed alongside. **Verified by breaking `api.js`, `app.js` and `data.js` in
  turn: each is now caught and named.**
- **A loop was swallowing failures.** `for f in ...; do node --check "$f"; done`
  exits with the last file's status, so a broken `api.js` would have passed as
  long as `data.js` parsed. Failures are collected explicitly.
- **A machine-local `node_modules` symlink had been committed**, pointing into a
  scratch directory on the machine the work was done on. `.gitignore` listed
  `node_modules/`, but a trailing slash matches directories only and a symlink
  is not one. Confirmed against a clean clone of `main`, which received a
  dangling symlink where `node_modules` belongs. Removed, and the pattern now
  covers both spellings.
- `scripts/ci.sh` holds every check CI runs and both jobs call it, so the
  workflow and a local run cannot drift into two different sets of checks.
- Added `workflow_dispatch`, and pinned the pip cache to
  `backend/pyproject.toml`.
- Recorded for the next person: every CI run between 0.5.0 and 0.6.0 failed
  three to four seconds after starting, with no runner assigned, no steps and no
  logs. That is GitHub declining to allocate a runner — an account-level Actions
  state, not a fault in the workflow — and no change to this repository can fix
  it.
- **The version drifted a second time.** The changelog said 0.6.0 while both
  `pyproject.toml` and the served `API_VERSION` said 0.5.0. The existing test
  bound the served version to the package but left the changelog free, so it
  passed. All three now read 0.6.1, and a test binds the changelog's newest
  heading to the package version — verified by pointing it at 0.9.9 and
  watching it fail.
- Verified against a clean clone on Python 3.12: ruff, format, strict mypy,
  migrations plus drift check, 137 tests, benchmark smoke, ESM syntax and the
  browser gate all pass.

## 0.6.0 — Deployable backend, enforced QA
- Added `backend/Dockerfile` and `docs/DEPLOYMENT.md`. The image installs only
  the API's dependencies — the benchmark runner's scikit-learn stack is never
  imported by the service — and runs `alembic upgrade head` before starting, as
  a non-root user, with a health check against `/health`.
  **Verified by installing the core dependency set into a clean environment and
  serving live requests from it; not built, since no Docker daemon was
  available.**
- The CI browser gate now exercises the interactions that used to be a manual
  QA list: home links resolve, search and category filters narrow the library,
  every benchmark URL loads, sliders change the stated requirements, volume
  moves the projected cost, the auditability toggle changes which methods
  qualify, chart and table agree on method count, the chart's table fallback
  matches, and keyboard focus reaches navigation, controls and chart points.
- **The gate was checked against a deliberately weakened evidence rule** and
  failed with four errors and a non-zero exit, so it is not passing vacuously.
- `docs/QA_CHECKLIST.md` is now fully ticked, and every item is machine-checked
  rather than asserted.
- `/health` reported an API version that had drifted from the package version.
  Fixed, and a test now holds the two together.
- Root `README.md` rewritten around what has actually been measured, including
  that neither measured method clears its problem's own requirement.
- `docs/IMPLEMENTATION_PLAN.md` marks real phase status instead of describing
  Phase 2 as upcoming.
- 136 tests pass.

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
