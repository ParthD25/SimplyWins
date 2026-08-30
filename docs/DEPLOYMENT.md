# Deployment

Two independently deployable pieces. The frontend works without the backend;
the backend never needs the frontend.

## Frontend — Vercel (live)

**https://simply-wins.vercel.app**

Static, no build step. The repository root `vercel.json` sets
`outputDirectory: frontend`, so the connected project serves the site whether
or not its Root Directory setting is configured.

To point the deployed site at an API, set the base URL before the module
scripts load — for example in `frontend/index.html`:

```html
<script>window.SIMPLESTWINS_API_BASE = 'https://api.example.com';</script>
```

With none set, the site renders bundled data and says so. That is a supported
state, not a degraded one: the portfolio deployment is expected to run this way
until a backend is hosted.

## Backend — container

`backend/Dockerfile` builds a runtime image. It deliberately installs only the
API's dependencies: the benchmark runner pulls scikit-learn and its native
stack, which the API never imports. Benchmarks run offline and their results
are promoted into the seed, so the served image stays small.

```bash
docker build -t simplestwins-api ./backend
docker run -p 8000:8000 \
  -e SIMPLESTWINS_DATABASE_URL="postgresql+psycopg://user:pass@host/simplestwins" \
  -e SIMPLESTWINS_CORS_ORIGINS="https://simply-wins.vercel.app" \
  simplestwins-api
```

The container runs `alembic upgrade head` before starting, so a fresh database
is usable on first boot. It runs as a non-root user and exposes a health check
against `/health`, which reports how many problems loaded rather than merely
that the process is alive.

### Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `SIMPLESTWINS_DATABASE_URL` | for Postgres | Defaults to local SQLite |
| `SIMPLESTWINS_CORS_ORIGINS` | yes | Comma-separated; must include the site's origin |
| `SIMPLESTWINS_SEED_VERSION` | no | Defaults to `v2` |
| `SIMPLESTWINS_LOG_LEVEL` | no | Defaults to `INFO` |

No secrets are needed. No model-provider credentials exist anywhere in the
project.

### Postgres

Add the driver, which is not a default dependency:

```bash
pip install "psycopg[binary]"
```

## Before exposing a public instance

Not yet built, and load-bearing if the API is opened to the internet:

- **Rate limiting.** Section 11 of `PROJECT_STANDARD.md` requires it on public
  run endpoints. The read endpoints are cheap, but nothing throttles them.
- **`POST /v1/runs`.** Deliberately absent. Executing benchmarks on demand
  costs money once a model provider is connected, so the endpoint should not
  exist until authentication and cost controls do.

The read-only API as it stands is safe to expose: it serves seeded definitions
and computes a pure function over caller-supplied requirements. It touches no
user data and holds no credentials.
