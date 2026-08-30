"""Executes a benchmark and writes an immutable run record.

Order matters here. Raw per-example predictions are written to disk *before*
aggregation, so a published score can always be recomputed from the artifact
rather than trusted. Section 4 of PROJECT_STANDARD.md lists what a run must
carry; ``RunRecord`` is that list made concrete.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.benchmarks import leakage
from app.benchmarks.base import BenchmarkMethod, Example, MethodConfig
from app.benchmarks.evaluation import (
    LATENCY_DEFINITION,
    METRIC_DEFINITION,
    METRIC_DEFINITION_VERSION,
    Scores,
    score,
)
from app.benchmarks.methods.keyword_rules import KeywordRulesMethod
from app.benchmarks.methods.llm_classifier import (
    LlmClassifierMethod,
    stratified_sample,
)
from app.benchmarks.registry import get_benchmark

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
# Every execution lands here; the directory is gitignored working output.
RUNS_ROOT = BACKEND_ROOT / "runs"
# Only runs promoted with `--publish` land here, and those are the ones the
# product may cite. Keeping them apart stops an exploratory run from being
# mistaken for a published result.
PUBLISHED_ROOT = BACKEND_ROOT / "benchmarks" / "published"


def _artifact_uri(path: Path) -> str:
    """Repo-relative when the run lives inside the checkout, absolute otherwise.

    A caller may legitimately point the runner at a directory outside the
    repository, so this must not assume containment.
    """
    try:
        return str(path.relative_to(BACKEND_ROOT))
    except ValueError:
        return str(path)


WARMUP_EXAMPLES = 5


@dataclass(frozen=True, slots=True)
class DatasetRef:
    name: str
    version: str
    sha256: str
    path: str
    license: str
    provenance: str
    total_examples: int
    train_examples: int
    test_examples: int


@dataclass(frozen=True, slots=True)
class RunRecord:
    """Everything needed to reproduce and audit one method's result."""

    run_id: str
    problem_slug: str
    benchmark_definition_version: str
    method_id: str
    method_name: str
    method_class: str
    complexity_rank: int
    implementation_version: str
    provider: str | None
    model_name: str | None
    model_version: str | None
    prompt_version: str | None
    dataset: DatasetRef
    code_commit_sha: str
    seed: int
    runtime: dict[str, str]
    started_at: str
    completed_at: str
    metric_definition: str
    metric_definition_version: str
    latency_definition: str
    result_state: str
    cost_state: str
    cost_model: dict[str, object]
    accuracy: float
    macro_f1: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_mean_ms: float
    cost_per_1k_usd: float
    # What the number was computed from, and whether the experiment could
    # have produced a low score at all. See app.benchmarks.leakage.
    leakage_audit: dict[str, object]
    deterministic: bool
    auditable: bool
    sample_count: int
    correct: int
    per_class: list[dict[str, object]]
    confusion: dict[str, dict[str, int]]
    raw_artifact_uri: str
    notes: str
    limitations: list[str]


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parents[2],
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # A run outside a checkout is still valid; the record says so rather
        # than carrying a fabricated SHA.
        return "unknown"


def _runtime() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "implementation": platform.python_implementation(),
    }


def load_dataset(slug: str) -> tuple[list[Example], list[Example], DatasetRef]:
    """Read the on-disk dataset for ``slug`` and verify its checksum.

    The module is resolved from the benchmark definition rather than imported by
    name, so registering a problem is the only step needed to make its corpus
    loadable.
    """
    definition = get_benchmark(slug)
    dataset_module = importlib.import_module(definition.dataset_module)

    path = dataset_module.DATASET_PATH
    if not path.is_file():
        raise FileNotFoundError(
            f"Dataset missing at {path}. Build it with `python -m {dataset_module.__name__}`."
        )
    payload = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    train: list[Example] = []
    test: list[Example] = []
    for line in payload.splitlines():
        row = json.loads(line)
        example = Example(example_id=row["example_id"], text=row["text"], label=row["label"])
        (train if row["split"] == "train" else test).append(example)

    source = dataset_module.SOURCE
    reference = DatasetRef(
        name=dataset_module.DATASET_NAME,
        version=dataset_module.DATASET_VERSION,
        sha256=digest,
        path=_artifact_uri(path),
        license=f"{source.license_name} ({source.license_url})",
        provenance=(
            f"Real corpus. {source.name} — {source.url}. {source.retrieved_note} "
            f"Split here at seed {dataset_module.SEED}, builder version "
            f"{dataset_module.GENERATOR_VERSION}."
        ),
        total_examples=len(train) + len(test),
        train_examples=len(train),
        test_examples=len(test),
    )
    return train, test, reference


def _leakage_audit(
    method: BenchmarkMethod,
    train: list[Example],
    evaluation_set: list[Example],
    labels: tuple[str, ...],
) -> dict[str, object]:
    """Run the checks that say whether this result could have come out low.

    For a keyword method the vocabulary is additionally split by whether each
    term occurs in the training corpus and the two halves are scored on their
    own. That is the check that caught this benchmark measuring its own author
    when the corpus was synthetic, and it stays wired in so the failure cannot
    return unnoticed.
    """
    provenance = None
    if isinstance(method, KeywordRulesMethod):
        terms = method.terms
        attested = leakage.attested_terms(terms, train)
        unattested = set(terms) - attested

        def accuracy(allowed: set[str]) -> float:
            restricted = method.with_terms(allowed)
            restricted.setup(MethodConfig(seed=0, labels=labels))
            predicted = restricted.predict(evaluation_set)
            hits = sum(1 for p, e in zip(predicted, evaluation_set, strict=True) if p == e.label)
            return round(hits / len(evaluation_set) * 100.0, 4)

        provenance = leakage.TermProvenance(
            total_terms=len(terms),
            attested_terms=len(attested),
            unattested_terms=len(unattested),
            accuracy_all_terms=accuracy(set(terms)),
            accuracy_attested_only=accuracy(attested),
            accuracy_unattested_only=accuracy(unattested),
        )

    return leakage.audit(
        train,
        evaluation_set,
        label_count=len(labels),
        term_provenance=provenance,
    ).as_dict()


def run_method(
    slug: str,
    method_id: str,
    *,
    seed: int = 20260830,
    runs_root: Path | None = None,
) -> RunRecord:
    """Fit, time, score, and persist one method against one dataset version."""
    definition = get_benchmark(slug)
    if method_id not in definition.methods:
        raise KeyError(f"Method {method_id!r} is not registered for {slug!r}")

    train, test, dataset = load_dataset(slug)
    labels = tuple(sorted({example.label for example in train + test}))

    method: BenchmarkMethod = definition.methods[method_id]()
    metadata = method.metadata()

    # Hosted tiers are billed per request, so they run on a stratified sample
    # rather than the full split. sample_count on the record always says how
    # many items produced the number, and it differs between methods.
    evaluation_set = test
    if isinstance(method, LlmClassifierMethod):
        evaluation_set = stratified_sample(test, size=definition.llm_sample_size, seed=seed)

    started_at = datetime.now(UTC)
    method.setup(MethodConfig(seed=seed, training_examples=tuple(train), labels=labels))

    # Warm up so the first timed call does not absorb import and cache costs.
    for example in evaluation_set[:WARMUP_EXAMPLES]:
        method.predict([example])

    predictions: list[str] = []
    latencies_ns: list[int] = []
    for example in evaluation_set:
        start = time.perf_counter_ns()
        predicted = method.predict([example])
        latencies_ns.append(time.perf_counter_ns() - start)
        predictions.append(predicted[0])
    completed_at = datetime.now(UTC)

    scores: Scores = score(
        [example.label for example in evaluation_set], predictions, latencies_ns, labels
    )

    # Computed before the record so the audit travels with the number it
    # qualifies, rather than being something a reader has to go and derive.
    audit = _leakage_audit(method, train, evaluation_set, labels)

    run_id = f"{slug}--{method_id}--{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = (runs_root or RUNS_ROOT) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Raw outputs land first; the aggregate is derived from what is on disk.
    artifact = run_dir / "predictions.jsonl"
    artifact.write_text(
        "".join(
            json.dumps(
                {
                    "example_id": example.example_id,
                    "gold": example.label,
                    "predicted": predicted,
                    "correct": example.label == predicted,
                    "latency_ns": latency,
                },
                sort_keys=True,
            )
            + "\n"
            for example, predicted, latency in zip(
                evaluation_set, predictions, latencies_ns, strict=True
            )
        ),
        encoding="utf-8",
    )

    record = RunRecord(
        run_id=run_id,
        problem_slug=slug,
        benchmark_definition_version=definition.definition_version,
        method_id=metadata.method_id,
        method_name=metadata.name,
        method_class=metadata.method_class,
        complexity_rank=metadata.complexity_rank,
        implementation_version=metadata.implementation_version,
        provider=metadata.provider,
        model_name=metadata.model_name,
        model_version=metadata.model_version,
        prompt_version=metadata.prompt_version,
        dataset=dataset,
        code_commit_sha=_git_sha(),
        seed=seed,
        runtime=_runtime(),
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        metric_definition=METRIC_DEFINITION,
        metric_definition_version=METRIC_DEFINITION_VERSION,
        latency_definition=LATENCY_DEFINITION,
        result_state="MEASURED",
        # Compute cost is projected from measured latency plus a rate
        # assumption, which makes it ESTIMATED even where the latency behind it
        # is MEASURED. A hosted model is the exception: it reports the tokens it
        # actually used, so its cost is arithmetic on observed usage.
        cost_state="MEASURED" if isinstance(method, LlmClassifierMethod) else "ESTIMATED",
        cost_model=asdict(metadata.cost_model),
        accuracy=round(scores.accuracy, 4),
        macro_f1=round(scores.macro_f1, 4),
        latency_p50_ms=round(scores.latency_p50_ms, 4),
        latency_p95_ms=round(scores.latency_p95_ms, 4),
        latency_mean_ms=round(scores.latency_mean_ms, 4),
        cost_per_1k_usd=round(
            method.measured_cost_per_1k(len(evaluation_set))
            if isinstance(method, LlmClassifierMethod)
            else metadata.cost_model.cost_per_1k(scores.latency_p50_ms),
            6,
        ),
        deterministic=metadata.deterministic,
        auditable=metadata.auditable,
        sample_count=scores.sample_count,
        correct=scores.correct,
        leakage_audit=audit,
        per_class=[asdict(entry) for entry in scores.per_class],
        confusion=scores.confusion,
        raw_artifact_uri=_artifact_uri(artifact),
        notes=metadata.notes,
        limitations=[
            "The dataset is synthetic, so difficulty reflects its generator rather "
            "than production support traffic.",
            "Only rules and traditional ML are implemented; no small-model or "
            "frontier-LLM result exists for this problem.",
            "Cost is projected from measured latency and a published compute rate, "
            "not from a billed invoice.",
        ],
    )

    (run_dir / "run.json").write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logger.info(
        "Benchmark run complete",
        extra={
            "run_id": run_id,
            "method_id": method_id,
            "accuracy": record.accuracy,
            "latency_p50_ms": record.latency_p50_ms,
        },
    )
    return record


def run_all(slug: str, *, seed: int = 20260830, runs_root: Path | None = None) -> list[RunRecord]:
    """Run every registered method for a problem against the same dataset version."""
    definition = get_benchmark(slug)
    return [
        run_method(slug, method_id, seed=seed, runs_root=runs_root)
        for method_id in definition.methods
    ]


def publish_run(record: RunRecord, published_root: Path | None = None) -> Path:
    """Promote a run to the citable record set.

    Copies both the aggregate and its raw predictions, so a published number can
    always be recomputed from the artifact that produced it.
    """
    import shutil

    root = (published_root or PUBLISHED_ROOT) / record.problem_slug
    root.mkdir(parents=True, exist_ok=True)

    (root / f"{record.method_id}.run.json").write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # raw_artifact_uri may be absolute for a run made outside the checkout.
    source = Path(record.raw_artifact_uri)
    if not source.is_absolute():
        source = BACKEND_ROOT / source
    if source.is_file():
        shutil.copyfile(source, root / f"{record.method_id}.predictions.jsonl")
    return root
