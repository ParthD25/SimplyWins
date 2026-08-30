# Benchmark runner

Executes implementation classes against one dataset version and one metric
definition, then writes an immutable record carrying everything section 4 of
`PROJECT_STANDARD.md` requires.

## Run

```bash
python -m app.benchmarks.cli list
python -m app.benchmarks.cli run support-ticket-routing
python -m app.benchmarks.cli run support-ticket-routing --method ticket-rules
python -m app.benchmarks.cli run support-ticket-routing --publish
```

Every execution writes to `backend/runs/<run_id>/` (gitignored). `--publish`
promotes a run to `backend/benchmarks/published/<slug>/`, which is the only
place the product may cite from — keeping exploratory runs from being mistaken
for published results.

## Adding a method

Implement the `BenchmarkMethod` protocol in `app/benchmarks/base.py`:

```python
def setup(self, config: MethodConfig) -> None: ...
def predict(self, examples: Sequence[Example]) -> Sequence[str]: ...
def metadata(self) -> MethodMetadata: ...
```

Then register it in `app/benchmarks/registry.py`. `setup()` receives the
training split; a deterministic method is free to ignore it.

Only methods that can actually execute are registered. The small-model and
frontier-LLM entries from the product spec are deliberately absent — listing a
method with no implementation would imply a result that does not exist.

## How measurement works

**Accuracy** is exact-match against the gold label, micro-averaged, plus macro
F1. No model grades anything: the task has labelled targets, so section 2 of the
standard requires a deterministic assertion.

**Latency** is wall-clock nanoseconds around a *single-example* `predict()`
call, after a warm-up pass, reported as p50 and p95. Single-example timing is
used because that is what a request-response deployment experiences. It gives
up the throughput advantage a vectorised method would enjoy in batch, which is
the honest comparison for this serving mode. Setup and training time are
excluded.

**Cost** is never measured. It is projected from measured p50 latency and a
published compute rate, so every cost figure is `ESTIMATED` under section 5 even
when the latency behind it is `MEASURED`. The rate, its source, and its date
travel with the number in `cost_model`.

## Reproducibility

Quality metrics reproduce exactly across runs on the same dataset version and
seed — verified. **Latency does not and cannot**: it is wall-clock timing on
shared hardware, so p50 moves by a few percent between runs. Treat latency as a
measurement with noise, not a constant.

## Current results — support-ticket-routing

Dataset v3.0.0 (`ba7087e2…`), 1,600 test examples, template-disjoint split.

| Method | Class | Accuracy | Macro F1 | p50 | p95 |
| --- | --- | --- | --- | --- | --- |
| `ticket-rules` | rules | 75.69% | 76.30% | ~0.11ms | ~0.19ms |
| `ticket-ml` | traditional-ml | 89.50% | 89.56% | ~0.71ms | ~0.94ms |

Accuracy and macro F1 are `MEASURED`. Latency is `MEASURED` but noisy. Cost is
`ESTIMATED`.

**Traditional ML wins this one.** On unseen phrasings, keyword rules give up
nearly 14 accuracy points. That contradicts the demo figures the frontend still
shows (rules 91.7%, ML 94.6%), which flattered the rules baseline — exactly the
kind of correction measuring is meant to produce.

The ML configuration (character n-grams, `C=1.0`) was selected on a
template-disjoint validation split carved from the *training* data. The test
split was never consulted during selection.

Read `datasets/support_ticket_routing/DATASET.md` before citing any of this —
the dataset is synthetic and its limitations are material.
