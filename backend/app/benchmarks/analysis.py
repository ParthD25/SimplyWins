"""Statistics over a benchmark's per-example predictions.

An accuracy figure is a point estimate from one sample. On its own it cannot
say whether two methods actually differ, whether a method is systematically
biased toward a label, or how much of the gap is sampling noise. This module
computes the quantities that answer those questions from the prediction
artifacts every run writes.

The estimators are implemented here rather than imported so the arithmetic is
readable and testable; only the binomial CDF comes from scipy.

Three choices worth stating, because each rules out a wrong alternative:

*Wilson intervals, not normal approximation.* The textbook interval
``p ± z·sqrt(p(1-p)/n)`` is badly wrong near 0 and 1 — it can produce bounds
below 0 or above 1, and its coverage collapses exactly where these methods live
(98.77% accuracy). Wilson stays inside [0, 1] and holds its coverage.

*McNemar's test, not two independent proportion tests.* Both methods are scored
on the *same* examples, so their errors are paired and correlated. Treating
them as independent samples ignores that pairing and overstates the uncertainty
in their difference. McNemar looks only at the examples where the two disagree,
which is the evidence that actually bears on which is better.

*The exact binomial form, not the chi-square approximation.* The approximation
needs a reasonably large discordant count; when two methods differ on a handful
of examples it is unreliable, which is the case where the answer matters most.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# 1.959963985 is the exact two-sided normal quantile at 95%; 1.96 is a rounding
# of it that shifts interval bounds in the fourth decimal.
Z_95 = 1.959963985


@dataclass(frozen=True, slots=True)
class Prediction:
    example_id: str
    gold: str
    predicted: str
    correct: bool
    latency_ns: int


@dataclass(frozen=True, slots=True)
class Interval:
    point: float
    low: float
    high: float

    def __str__(self) -> str:
        return f"{self.point * 100:.2f}% [{self.low * 100:.2f}, {self.high * 100:.2f}]"


def load_predictions(path: Path) -> list[Prediction]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(
            Prediction(
                example_id=row["example_id"],
                gold=row["gold"],
                predicted=row["predicted"],
                correct=bool(row["correct"]),
                latency_ns=int(row.get("latency_ns", 0)),
            )
        )
    return rows


def wilson_interval(successes: int, trials: int, z: float = Z_95) -> Interval:
    """Wilson score interval for a binomial proportion.

    Derived by inverting the score test: rather than centring on the observed
    proportion, it asks which true proportions would not have been rejected by
    the data. That is what keeps it inside [0, 1] and well-behaved at the
    extremes.
    """
    if trials == 0:
        return Interval(0.0, 0.0, 0.0)
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    margin = z / denominator * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return Interval(point=p, low=max(0.0, centre - margin), high=min(1.0, centre + margin))


@dataclass(frozen=True, slots=True)
class McNemar:
    """Paired comparison of two classifiers on the same examples.

    ``only_a`` and ``only_b`` are the discordant counts: examples one method got
    right and the other did not. Examples both got right, or both got wrong,
    carry no information about which is better and are excluded by construction.
    """

    both_correct: int
    only_a: int
    only_b: int
    both_wrong: int
    p_value: float
    test: str

    @property
    def discordant(self) -> int:
        return self.only_a + self.only_b


def mcnemar(a: Sequence[Prediction], b: Sequence[Prediction]) -> McNemar:
    """Exact two-sided McNemar test.

    Under the null hypothesis that the two methods are equally likely to be the
    one that gets a disagreed-upon example right, each discordant example is a
    fair coin flip, so the count favouring either method is Binomial(n, 0.5).
    """
    from scipy.stats import binom

    by_id_b = {p.example_id: p for p in b}
    both_correct = only_a = only_b = both_wrong = 0
    for pred_a in a:
        pred_b = by_id_b.get(pred_a.example_id)
        if pred_b is None:
            continue
        if pred_a.correct and pred_b.correct:
            both_correct += 1
        elif pred_a.correct:
            only_a += 1
        elif pred_b.correct:
            only_b += 1
        else:
            both_wrong += 1

    # Two-sided: twice the tail beyond the smaller count, capped at 1. With no
    # disagreements there is no evidence either way, so p is 1 by definition.
    n = only_a + only_b
    p_value = 1.0 if n == 0 else min(1.0, 2 * float(binom.cdf(min(only_a, only_b), n, 0.5)))

    return McNemar(
        both_correct=both_correct,
        only_a=only_a,
        only_b=only_b,
        both_wrong=both_wrong,
        p_value=p_value,
        test="exact binomial",
    )


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    label: str
    support: int
    predicted: int
    precision: float
    recall: float
    f1: float

    @property
    def prediction_ratio(self) -> float:
        """How often the method predicts this label, relative to how often it is
        the truth. Above 1 means the method over-uses the label."""
        return self.predicted / self.support if self.support else 0.0


def per_class(predictions: Sequence[Prediction]) -> list[ClassMetrics]:
    labels = sorted({p.gold for p in predictions} | {p.predicted for p in predictions})
    metrics = []
    for label in labels:
        tp = sum(1 for p in predictions if p.gold == label and p.predicted == label)
        fp = sum(1 for p in predictions if p.gold != label and p.predicted == label)
        fn = sum(1 for p in predictions if p.gold == label and p.predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics.append(
            ClassMetrics(
                label=label,
                support=tp + fn,
                predicted=tp + fp,
                precision=precision,
                recall=recall,
                f1=f1,
            )
        )
    return metrics


@dataclass(frozen=True, slots=True)
class PriorBias:
    """Whether a method's output distribution matches the truth's.

    A method can be accurate overall and still systematically over-use one
    label; on a balanced corpus that shows up here as a ratio far from 1 even
    when accuracy looks respectable.
    """

    chi_square: float
    degrees_of_freedom: int
    p_value: float
    most_overused: str
    most_overused_ratio: float
    most_underused: str
    most_underused_ratio: float


def prior_bias(metrics: Sequence[ClassMetrics]) -> PriorBias:
    """Chi-square goodness of fit of predicted counts against true counts."""
    from scipy.stats import chi2

    statistic = 0.0
    for entry in metrics:
        if entry.support == 0:
            continue
        statistic += (entry.predicted - entry.support) ** 2 / entry.support
    dof = max(1, len(metrics) - 1)
    p_value = float(chi2.sf(statistic, dof))

    ranked = sorted((m for m in metrics if m.support), key=lambda m: m.prediction_ratio)
    return PriorBias(
        chi_square=statistic,
        degrees_of_freedom=dof,
        p_value=p_value,
        most_overused=ranked[-1].label,
        most_overused_ratio=ranked[-1].prediction_ratio,
        most_underused=ranked[0].label,
        most_underused_ratio=ranked[0].prediction_ratio,
    )


def confusion_pairs(predictions: Sequence[Prediction], top: int = 5) -> list[tuple[str, str, int]]:
    """The most frequent (true, predicted) mistakes, largest first."""
    counts: Counter[tuple[str, str]] = Counter()
    for p in predictions:
        if p.gold != p.predicted:
            counts[(p.gold, p.predicted)] += 1
    return [(gold, predicted, n) for (gold, predicted), n in counts.most_common(top)]


def accuracy_by_length(
    predictions: Sequence[Prediction], texts: dict[str, str], buckets: int = 4
) -> list[tuple[str, int, Interval]]:
    """Accuracy within length quartiles.

    A method that degrades on longer inputs is not uniformly accurate, and an
    overall figure hides that.
    """
    sized = [(len(texts.get(p.example_id, "")), p) for p in predictions]
    sized = [entry for entry in sized if entry[0] > 0]
    if not sized:
        return []
    sized.sort(key=lambda entry: entry[0])

    out = []
    size = len(sized) // buckets
    for index in range(buckets):
        start = index * size
        stop = len(sized) if index == buckets - 1 else (index + 1) * size
        chunk = sized[start:stop]
        if not chunk:
            continue
        correct = sum(1 for _, p in chunk if p.correct)
        label = f"{chunk[0][0]}-{chunk[-1][0]} chars"
        out.append((label, len(chunk), wilson_interval(correct, len(chunk))))
    return out


def paired_bootstrap(
    a: Sequence[Prediction],
    b: Sequence[Prediction],
    *,
    iterations: int = 10_000,
    seed: int = 20260830,
) -> Interval:
    """Confidence interval for the accuracy difference (b − a).

    Examples are resampled together rather than separately, because the two
    methods were scored on the same items; resampling independently would break
    the pairing the comparison depends on.
    """
    import numpy as np

    by_id_b = {p.example_id: p for p in b}
    paired = [(p.correct, by_id_b[p.example_id].correct) for p in a if p.example_id in by_id_b]
    if not paired:
        return Interval(0.0, 0.0, 0.0)

    left = np.array([x for x, _ in paired], dtype=float)
    right = np.array([y for _, y in paired], dtype=float)
    observed = float(right.mean() - left.mean())

    rng = np.random.default_rng(seed)
    n = len(paired)
    indices = rng.integers(0, n, size=(iterations, n))
    diffs = right[indices].mean(axis=1) - left[indices].mean(axis=1)
    low, high = np.percentile(diffs, [2.5, 97.5])
    return Interval(point=observed, low=float(low), high=float(high))


def fallback_rate(predictions: Sequence[Prediction], fallback_label: str) -> float:
    """How often a rules method fell through to its default answer.

    A high rate means the vocabulary matched nothing, so the method is guessing
    under a different name.
    """
    if not predictions:
        return 0.0
    return sum(1 for p in predictions if p.predicted == fallback_label) / len(predictions)


@dataclass(frozen=True, slots=True)
class ErrorProjection:
    """What a method's error rates mean at the operating volume.

    Accuracy is a rate; a decision is made on counts. Two methods differing by
    seven accuracy points differ by hundreds of thousands of incidents a month
    at scale, and the two kinds of error are rarely equally costly — a spam
    filter's false positive hides a real message from someone, while its false
    negative merely lets junk through.
    """

    label: str
    monthly_volume: int
    false_positives: float
    false_negatives: float
    false_positive_rate: float

    @property
    def total_errors(self) -> float:
        return self.false_positives + self.false_negatives


def project_errors(
    metrics: Sequence[ClassMetrics],
    label: str,
    *,
    monthly_volume: int,
    sample_size: int,
) -> ErrorProjection:
    """Scale the observed confusion for one label up to a month of traffic."""
    entry = next((m for m in metrics if m.label == label), None)
    if entry is None or sample_size == 0:
        return ErrorProjection(label, monthly_volume, 0.0, 0.0, 0.0)

    true_positives = entry.recall * entry.support
    false_positives = entry.predicted - true_positives
    false_negatives = entry.support - true_positives
    negatives = sample_size - entry.support

    scale = monthly_volume / sample_size
    return ErrorProjection(
        label=label,
        monthly_volume=monthly_volume,
        false_positives=false_positives * scale,
        false_negatives=false_negatives * scale,
        false_positive_rate=(false_positives / negatives) if negatives else 0.0,
    )
