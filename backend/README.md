# SimplyWins Backend

FastAPI service that owns the benchmark problem definitions and applies the
SimplyWins decision rule: **the lowest-complexity method that satisfies every
hard operating requirement wins, and when nothing satisfies them, nothing wins.**

Phase 2 (Backend Foundation) and the first half of Phase 3 (benchmark runner)
are complete. **No model-provider API is connected.** The runner executes the
methods that can run locally — deterministic rules and traditional ML — and
`support-ticket-routing` now has genuinely measured results. See
`app/benchmarks/README.md`.

## Install

Requires Python 3.12+.

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`uv` works too, and is faster:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

## Run

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The database is created and seeded on startup. Interactive API docs are at
`http://localhost:8000/docs`.

## Test

```bash
.venv/bin/python -m pytest          # 135 tests
.venv/bin/ruff check .              # lint
.venv/bin/ruff format --check .     # formatting
.venv/bin/mypy app                  # strict type check
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness plus the number of seeded problems |
| `GET` | `/v1/problems` | Problem summaries |
| `GET` | `/v1/problems/{slug}` | One problem: dataset, default requirements, methods, results |
| `POST` | `/v1/problems/{slug}/recommend` | Apply the decision rule to caller-supplied requirements |

Errors always use the envelope required by section 6 of `PROJECT_STANDARD.md`:

```json
{ "error": { "code": "problem_not_found", "message": "...", "details": {} } }
```

## Architecture

```
app/
  main.py            FastAPI app, lifespan, /health
  config.py          Settings from environment variables
  db.py              Engine and session factory (the only place a connection is built)
  errors.py          Application errors and the single error envelope
  logging_config.py  JSON formatter over the standard logging module
  api/v1/            HTTP routing only, no business logic
  domain/            The decision rule: pure, no I/O, no framework imports
  services/          Orchestration and ORM-to-schema translation
  repositories/      Persistence behind a Protocol
  models/            SQLAlchemy ORM models
  schemas/           Pydantic v2 API payloads
  seed/v1/           Versioned problem definitions
```

The layering exists to keep one rule enforceable: **the decision rule must be
testable without a database or an HTTP client.** `app/domain/recommendation.py`
imports nothing from FastAPI, SQLAlchemy, or the rest of the app, so the
product's central claim is verified by pure unit tests.

Route handlers delegate to services and contain no logic. Services depend on the
`ProblemRepository` protocol rather than a concrete session.

## Why SQLAlchemy 2.x rather than SQLModel

Both were acceptable per the build prompt. SQLAlchemy 2.x was chosen because
SQLModel fuses the persistence model and the API schema into a single class.
That is convenient, but it makes it easy for a database column to leak into a
public payload — precisely what section 8 of `PROJECT_STANDARD.md` ("separate
domain logic from transport") forbids, and what would let a schema change
silently break the `/v1` contract. Keeping ORM models (`app/models/`) and
Pydantic schemas (`app/schemas/`) as distinct types makes the translation
explicit and puts it in one place (`app/services/problem_service.py`).

Cost: one hand-written mapping per entity. That is a deliberate trade for a
contract that cannot drift by accident.

## Database

SQLite locally, created at `backend/simplestwins.db` (gitignored). PostgreSQL is
intended for deployment; only the URL changes:

```bash
export SIMPLESTWINS_DATABASE_URL="postgresql+psycopg://user:pass@host/simplestwins"
```

### Migrations

Alembic reads the same `SIMPLESTWINS_DATABASE_URL` the app does, so a migration
can never run against a different database than the service.

```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "what changed" # after a model change
alembic check                                     # fail if models have drifted
```

`create_all` still builds the schema for local development and tests. A test
asserts the two paths produce identical tables and columns, and another runs
`alembic check`, so a model change that never got a migration fails CI rather
than reaching production as a missing column.

## Seed data

`app/seed/v2/problems.json` holds the six MVP problem definitions, with the
methods that have been benchmarked promoted to `MEASURED`.

Measured results reach the seed by a reproducible command, never by hand:

```bash
python -m app.seed.promote --from v1 --to v2
```

It reads `benchmarks/published/<slug>/*.run.json` and writes the next seed
version with those methods carrying their run id, dataset checksum, raw
artifact path and sample count. A method with no published run keeps its `DEMO`
figures, which is why `support-ticket-routing` sits at 2 of 4 measured and
still produces no recommendation.

The original `app/seed/v1/problems.json` is kept as the all-`DEMO` baseline. The backend
owns them from this phase onward; `frontend/assets/data.js` keeps its copy only
so the static prototype stays viewable offline. The two were verified identical
on every shared field at the time of migration.

Seeding runs on startup and is idempotent at the problem level: a slug that is
already stored is left alone rather than overwritten, so restarting never
silently mutates a stored definition. To change a definition, add a new
versioned directory (`app/seed/v2/`) and point `SIMPLESTWINS_SEED_VERSION` at
it rather than editing `v1` in place.

**Every seeded figure is `DEMO` data.** Nothing here was measured. The API says
so on every result (`result_state`) and on every recommendation
(`data_state_notice`), and tests assert it stays that way.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SIMPLESTWINS_DATABASE_URL` | `sqlite+pysqlite:///./simplestwins.db` | Database connection |
| `SIMPLESTWINS_SEED_VERSION` | `v1` | Which seed directory to load |
| `SIMPLESTWINS_CORS_ORIGINS` | localhost dev origins | Comma-separated allowed origins |
| `SIMPLESTWINS_LOG_LEVEL` | `INFO` | Root log level |

No secrets are needed in this phase. When one is (Phase 3, model providers), it
arrives through the environment and is never committed.

## Where this phase stops

Deliberately **not** built, and not to be added without explicit approval:

- any model-provider API call (OpenAI, Anthropic, Hugging Face, or otherwise)
- the benchmark runner and the `BenchmarkMethod` protocol
- `POST /v1/runs` and `GET /v1/runs/{run_id}` — the `BenchmarkRun` table exists
  so the provenance columns are defined alongside the data model, but nothing
  writes to it
- authentication, rate limiting, and the public-run cost controls that
  `docs/BACKEND_CONTRACT.md` requires before run endpoints are exposed
- replacing the frontend's local `data.js` with live `/v1` fetches (Phase 5)

Next: decide how measured results reach the API. Two of four methods on
`support-ticket-routing` are now `MEASURED`; the other two remain `DEMO`
because no model provider is connected. Blending states inside one comparison
would produce a recommendation drawn from a mix of evidence and illustration,
so that integration needs a deliberate decision rather than a quiet merge.
