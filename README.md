# SimplyWins

**Does this actually need AI?**

SimplyWins benchmarks several technical approaches to the same task and
recommends the least-complex one that satisfies the real operating
requirements — or declines to recommend anything, when the evidence does not
support a choice.

**Live:** https://simply-wins.vercel.app

## The rule that governs everything

> No value may influence a SimplyWins recommendation unless its provenance
> state is `MEASURED`. A benchmark whose method set mixes provenance states
> cannot produce a final recommendation.

Section 3.1 of [`PROJECT_STANDARD.md`](PROJECT_STANDARD.md). It is enforced in
the backend, mirrored in the frontend, and verified in a real browser by CI.
Illustrative figures are shown for context, visibly separated, and excluded
from every ranking, tie-break, and Pareto frontier.

## What has actually been measured

Three problems, each against a real corpus published by someone else. Two of
the four method tiers are measured on every one; the two hosted-model tiers
have never been run, because no API key is configured.

| Problem | Corpus | Rules | TF-IDF + logreg | Chance | Commonest label |
| --- | --- | ---: | ---: | ---: | ---: |
| Support request routing | CFPB complaints, 7 queues | 46.43% | **79.87%** | 14.29% | 14.29% |
| Spam detection | UCI SMS Spam | 92.06% | **98.77%** | 50.00% | 87.54% |
| Sentiment | SST-2 film reviews | 59.33% | **78.83%** | 50.00% | 51.63% |

Every figure is scored on a held-out split with zero train/test overlap, and
every one is published beside the floors it had to beat — because an accuracy
number is only evidence if the experiment could have produced a low one.

Read the middle two columns against the right two. Keyword rules on spam look
strong at 92.06% until you notice that answering "ham" every time scores 87.54%,
so the entire vocabulary buys four and a half points. On routing they reach
46.43% where a trained linear model reaches 79.87% — a 33-point gap that says
this job is not a rules job. On sentiment the lexicon barely clears a coin flip.

No problem names a winner, because two of four methods are unrun on each and an
unrun method could displace the current leader.

**The accuracy column is the least interesting one.** Traditional ML beats
keyword rules on all three problems at McNemar p < 1e-22, so none of those gaps
is noise — but the error *profiles* say more than the rates do:

- On spam, rules reach 92.06% with a precision on spam of 0.636. At the stated
  5M messages a month that is **303,422 legitimate messages wrongly flagged**,
  against 22,595 for the model — 13x more, out of a 6.7-point accuracy gap.
- On sentiment, the rules baseline answers "positive" for 88.5% of inputs where
  the truth is 51.6% positive, and catches one negative in five. Its 59.33% is
  a majority-class predictor with extra steps.
- The routing model is statistically unbiased across seven queues (chi-square
  1.3 on 6 df, p = 0.97), and its errors sit in semantically adjacent pairs —
  mortgage against loans, money-transfer against bank-account — which is label
  noise in the corpus rather than model failure.

[`docs/ANALYSIS.md`](docs/ANALYSIS.md) has the full output: Wilson intervals,
McNemar tests, per-class precision and recall, prior-bias chi-squares, error
projections at operating volume, and accuracy by input length.

## Why the earlier numbers were deleted

An earlier version of this benchmark ran on text generated in this repository,
and its keyword baseline was written by the same author. It scored 78.9%. Then
the vocabulary was split by whether each term also appeared in the generator's
own templates:

| Vocabulary | Accuracy |
| --- | ---: |
| All 106 keywords | 78.9% |
| Only the 78 that appear in the corpus | 78.9% |
| Only the 28 that do not | 25.3% |
| Chance | 20.0% |

Every point came from words the author had put on both sides of the experiment.
The benchmark was measuring its author. The file asserting that the vocabulary
had been chosen "without consulting the dataset generator's phrasings" was
false and is gone, along with the synthetic corpus and the five problems that
had no measurements at all.

That check now runs on every benchmark and is published on the site, so the
failure cannot return unnoticed.

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

# Datasets — downloaded from their public sources, then split deterministically
.venv/bin/python -m app.benchmarks.datasets.cfpb_complaints.build
.venv/bin/python -m app.benchmarks.datasets.sms_spam.build
.venv/bin/python -m app.benchmarks.datasets.sst2_sentiment.build

# Benchmarks, then the seed and the frontend's bundled copy
.venv/bin/python -m app.benchmarks.cli run spam-detection --method rules --publish
.venv/bin/python -m app.seed.build_seed --to v3
.venv/bin/python -m app.seed.export_frontend
```

The frontend falls back to bundled data when no backend is configured, and says
so on the page. Set `window.SIMPLESTWINS_API_BASE` to point it at an API.

## Checks

```bash
scripts/ci.sh              # everything CI runs
scripts/ci.sh backend      # lint, format, types, migration drift, 197 tests, benchmark smoke
scripts/ci.sh frontend     # ESM syntax, then 5 pages x 2 widths in a real browser
```

GitHub Actions installs dependencies and then calls this same script, so a green
run here is the same set of checks — there is no second copy in the workflow YAML
to drift from it. The backend half expects `pip install -e ".[dev]"` to have been
run and its `bin/` on `PATH`; the frontend half expects
`npm install --no-save playwright`.

## What is deliberately not built

- **No model provider is connected.** The small-model and frontier-LLM tiers
  are implemented against the Anthropic SDK but have never run: without
  `ANTHROPIC_API_KEY` their `setup()` raises rather than estimating anything.
  That is why every benchmark reports `BENCHMARK_INCOMPLETE`.
- **`POST /v1/runs` does not exist.** Running benchmarks on demand costs money
  once a provider is connected; the endpoint should not exist before
  authentication and cost controls do.
- **Three problems, not twelve.** Each is backed by a real corpus with a
  [dataset card](backend/app/benchmarks/datasets/cfpb_complaints/DATASET.md)
  stating its own limitations — the CFPB labels carry genuine noise, since a
  complaint about a maturing certificate of deposit is filed under money
  transfer. Adding a problem means finding a real corpus for it, not writing
  one.
- **No document or OCR problems.** Invoice and receipt extraction were in the
  original plan and are absent, because they need licensed document corpora
  that have not been sourced.

## Documents

- [`PROJECT_STANDARD.md`](PROJECT_STANDARD.md) — the constitution
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — phase status
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — how to deploy each piece
- [`backend/app/benchmarks/README.md`](backend/app/benchmarks/README.md) — how measurement works
- [`CHANGELOG.md`](CHANGELOG.md)
