"""Deterministic scoring.

No LLM grades anything here. The task has labelled targets, so the metric is a
plain comparison — section 2 of PROJECT_STANDARD.md forbids using a model to
judge when a deterministic assertion is available.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Bumped whenever the definition below changes, so old runs stay comparable
# only against runs carrying the same version.
METRIC_DEFINITION_VERSION = "1.0.0"
METRIC_DEFINITION = (
    "accuracy = exact-match of predicted label against the gold label, "
    "micro-averaged over every example in the evaluation split; "
    "macro_f1 = unweighted mean of per-class F1."
)
LATENCY_DEFINITION = (
    "Wall-clock nanoseconds around a single-example predict() call, measured "
    "with time.perf_counter_ns() in-process after a warm-up pass. Reported as "
    "the median (p50) and 95th percentile over the evaluation split. Model "
    "setup and training time are excluded."
)


@dataclass(frozen=True, slots=True)
class ClassScore:
    label: str
    support: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True, slots=True)
class Scores:
    sample_count: int
    correct: int
    accuracy: float
    macro_f1: float
    per_class: tuple[ClassScore, ...]
    confusion: dict[str, dict[str, int]]
    latency_p50_ms: float
    latency_p95_ms: float
    latency_mean_ms: float


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile.

    Chosen over interpolation so the reported number is always a latency that
    actually occurred, which keeps the figure defensible.
    """
    if not sorted_values:
        return 0.0
    rank = max(1, min(len(sorted_values), round(fraction * len(sorted_values) + 0.5)))
    return sorted_values[rank - 1]


def score(
    gold: Sequence[str],
    predicted: Sequence[str],
    latencies_ns: Sequence[int],
    labels: Sequence[str],
) -> Scores:
    if not (len(gold) == len(predicted) == len(latencies_ns)):
        raise ValueError(
            f"length mismatch: gold={len(gold)} predicted={len(predicted)} "
            f"latencies={len(latencies_ns)}"
        )
    if not gold:
        raise ValueError("cannot score an empty evaluation split")

    ordered_labels = tuple(labels)
    confusion = {actual: dict.fromkeys(ordered_labels, 0) for actual in ordered_labels}
    correct = 0
    for actual, prediction in zip(gold, predicted, strict=True):
        if prediction not in confusion[actual]:
            # A method that invents a label is a bug, not a low score.
            raise ValueError(f"method predicted unknown label {prediction!r}")
        confusion[actual][prediction] += 1
        if actual == prediction:
            correct += 1

    per_class = []
    for label in ordered_labels:
        true_positive = confusion[label][label]
        support = sum(confusion[label].values())
        predicted_count = sum(confusion[actual][label] for actual in ordered_labels)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class.append(
            ClassScore(label=label, support=support, precision=precision, recall=recall, f1=f1)
        )

    latencies_ms = sorted(value / 1_000_000 for value in latencies_ns)
    return Scores(
        sample_count=len(gold),
        correct=correct,
        accuracy=100.0 * correct / len(gold),
        macro_f1=100.0 * sum(entry.f1 for entry in per_class) / len(per_class),
        per_class=tuple(per_class),
        confusion=confusion,
        latency_p50_ms=_percentile(latencies_ms, 0.50),
        latency_p95_ms=_percentile(latencies_ms, 0.95),
        latency_mean_ms=sum(latencies_ms) / len(latencies_ms),
    )
