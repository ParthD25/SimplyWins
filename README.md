# SimplestWins

**Does this actually need AI?**

SimplestWins benchmarks several technical approaches to the same task and
recommends the least-complex one that satisfies the real operating
requirements — or declines to recommend anything, when the evidence does not
support a choice.

**Live:** https://simply-wins.vercel.app

## The rule that governs everything

> No value may influence a SimplestWins recommendation unless its provenance
> state is `MEASURED`. A benchmark whose method set mixes provenance states
> cannot produce a final recommendation.

Section 3.1 of [`PROJECT_STANDARD.md`](PROJECT_STANDARD.md). It is enforced in
the backend, mirrored in the frontend, and verified in a real browser by CI.
Illustrative figures are shown for context, visibly separated, and excluded
from every ranking, tie-break, and Pareto frontier.

## What has actually been measured

One benchmark, two of its four methods, on 1,600 held-out examples:

| Method | Accuracy | Macro F1 | p50 latency | State |
| --- | --- | --- | --- | --- |
| Keyword + priority rules | 75.69% | 76.30% | ~0.11ms | MEASURED |
| TF-IDF + logistic regression | 89.50% | 89.56% | ~0.71ms | MEASURED |
| Small local model | — | — | — | not implemented |
| Frontier LLM | — | — | — | not implemented |

**Neither measured method clears the problem's own 92% accuracy requirement.**
The illustrative figures this replaced claimed 91.7% and 94.6% — that both
passed. They do not. So `support-ticket-routing` reports
`BENCHMARK_INCOMPLETE`, names no winner, and says "2 of 4 methods measured".

Everything else in the product is still `DEMO` data and labelled as such.

Accuracy and macro F1 reproduce exactly across runs. Latency is measured but
varies a few percent, being wall-clock timing. Cost is `ESTIMATED` — projected
from measured latency plus a dated compute rate — and never claimed otherwise.

## Layout

```
frontend/     Static site. No build step. Works with or without the backend.
backend/      FastAPI service, benchmark runner, datasets, migrations.
docs/         Product spec, data model, API contract, deployment, QA.
ci/           Browser gate.
scripts/      ci.sh — every check CI runs, runnable locally.
```

## Run it

```bash
# Frontend
python -m http.server 8000 -d frontend

# Backend
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload

# Benchmarks
.venv/bin/python -m app.benchmarks.cli run support-ticket-routing --publish
.venv/bin/python -m app.seed.promote --from v1 --to v2
```

The frontend falls back to bundled data when no backend is configured, and says
so on the page. Set `window.SIMPLESTWINS_API_BASE` to point it at an API.

## Checks

```bash
scripts/ci.sh              # everything CI runs
scripts/ci.sh backend      # lint, format, types, migration drift, 137 tests, benchmark smoke
scripts/ci.sh frontend     # ESM syntax, then 5 pages x 2 widths in a real browser
```

GitHub Actions installs dependencies and then calls this same script, so a green
run here is the same set of checks — there is no second copy in the workflow YAML
to drift from it. The backend half expects `pip install -e ".[dev]"` to have been
run and its `bin/` on `PATH`; the frontend half expects
`npm install --no-save playwright`.

## What is deliberately not built

- **No model provider is connected.** The small-model and frontier-LLM methods
  have no implementation, which is why no benchmark is complete.
- **`POST /v1/runs` does not exist.** Running benchmarks on demand costs money
  once a provider is connected; the endpoint should not exist before
  authentication and cost controls do.
- **No rate limiting**, so the API is not ready to be exposed publicly.
- **The dataset is synthetic.** Its
  [card](backend/app/benchmarks/datasets/support_ticket_routing/DATASET.md)
  records five material limitations. Replacing it with a real, licensed corpus
  is the most valuable next step.

## Documents

- [`PROJECT_STANDARD.md`](PROJECT_STANDARD.md) — the constitution
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — phase status
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — how to deploy each piece
- [`backend/app/benchmarks/README.md`](backend/app/benchmarks/README.md) — how measurement works
- [`CHANGELOG.md`](CHANGELOG.md)
