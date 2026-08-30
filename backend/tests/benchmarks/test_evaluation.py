"""Scoring must be exactly right — every published number depends on it."""

from __future__ import annotations

import pytest

from app.benchmarks.evaluation import score

LABELS = ("a", "b", "c")


def test_perfect_predictions_score_100() -> None:
    result = score(["a", "b", "c"], ["a", "b", "c"], [1, 2, 3], LABELS)

    assert result.accuracy == 100.0
    assert result.macro_f1 == 100.0
    assert result.correct == 3


def test_all_wrong_scores_zero() -> None:
    result = score(["a", "a"], ["b", "b"], [1, 2], LABELS)

    assert result.accuracy == 0.0
    assert result.correct == 0


def test_accuracy_is_micro_averaged() -> None:
    result = score(["a"] * 3 + ["b"], ["a", "a", "b", "b"], [1, 2, 3, 4], LABELS)

    assert result.accuracy == pytest.approx(75.0)


def test_macro_f1_weights_classes_equally() -> None:
    """A rare class carries the same weight as a common one, so a method that
    ignores it cannot hide behind overall accuracy."""
    gold = ["a"] * 9 + ["b"]
    predicted = ["a"] * 10

    result = score(gold, predicted, list(range(10)), ("a", "b"))

    assert result.accuracy == pytest.approx(90.0)
    assert result.macro_f1 < 50.0


def test_confusion_matrix_records_every_pair() -> None:
    result = score(["a", "a", "b"], ["a", "b", "b"], [1, 2, 3], ("a", "b"))

    assert result.confusion == {"a": {"a": 1, "b": 1}, "b": {"a": 0, "b": 1}}


def test_per_class_precision_and_recall() -> None:
    result = score(["a", "a", "b"], ["a", "b", "b"], [1, 2, 3], ("a", "b"))
    by_label = {entry.label: entry for entry in result.per_class}

    assert by_label["a"].recall == pytest.approx(0.5)
    assert by_label["a"].precision == pytest.approx(1.0)
    assert by_label["b"].precision == pytest.approx(0.5)


def test_percentiles_report_latencies_that_actually_occurred() -> None:
    latencies_ns = [n * 1_000_000 for n in (10, 20, 30, 40, 100)]

    result = score(["a"] * 5, ["a"] * 5, latencies_ns, ("a",))

    assert result.latency_p50_ms in {20.0, 30.0}
    assert result.latency_p95_ms == 100.0


def test_unknown_predicted_label_is_an_error_not_a_low_score() -> None:
    with pytest.raises(ValueError, match="unknown label"):
        score(["a"], ["zzz"], [1], LABELS)


def test_length_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        score(["a", "b"], ["a"], [1, 2], LABELS)


def test_empty_split_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty evaluation split"):
        score([], [], [], LABELS)
