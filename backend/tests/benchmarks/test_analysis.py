"""The statistics, checked against values derivable by hand.

Every estimator here is verified against a case whose answer is known
independently, because an analysis module that is merely self-consistent can be
confidently wrong.
"""

from __future__ import annotations

import math

import pytest

from app.benchmarks.analysis import (
    Prediction,
    accuracy_by_length,
    confusion_pairs,
    fallback_rate,
    mcnemar,
    paired_bootstrap,
    per_class,
    prior_bias,
    wilson_interval,
)


def _p(example_id: str, gold: str, predicted: str) -> Prediction:
    return Prediction(example_id, gold, predicted, gold == predicted, 1000)


class TestWilsonInterval:
    def test_matches_the_closed_form(self) -> None:
        """Recomputed by hand for 80/100 at z=1.959963985."""
        interval = wilson_interval(80, 100)
        assert interval.point == 0.8
        assert interval.low == pytest.approx(0.7111708344, abs=1e-9)
        assert interval.high == pytest.approx(0.8666330667, abs=1e-9)

    def test_is_symmetric_under_swapping_success_and_failure(self) -> None:
        """An independent property check: the interval for k of n successes must
        mirror the interval for n-k. If the algebra were wrong this would almost
        certainly break, and it does not depend on any constant I typed in."""
        for successes, trials in [(0, 20), (3, 20), (7, 31), (99, 100)]:
            direct = wilson_interval(successes, trials)
            mirrored = wilson_interval(trials - successes, trials)
            assert direct.low == pytest.approx(1 - mirrored.high, abs=1e-12)
            assert direct.high == pytest.approx(1 - mirrored.low, abs=1e-12)

    def test_stays_inside_the_unit_interval_at_the_extremes(self) -> None:
        """The normal approximation fails here — for 100/100 it gives the
        degenerate [1.0, 1.0], and for 0/100 it gives [0, 0]."""
        perfect = wilson_interval(100, 100)
        # Exactly 1 in the algebra; a rounding step below it in floating point.
        assert perfect.high == pytest.approx(1.0, abs=1e-12)
        assert 0.0 < perfect.low < 1.0

        none = wilson_interval(0, 100)
        assert none.low == 0.0
        assert 0.0 < none.high < 1.0

    def test_narrows_as_the_sample_grows(self) -> None:
        small = wilson_interval(45, 50)
        large = wilson_interval(4500, 5000)
        assert (large.high - large.low) < (small.high - small.low)

    def test_zero_trials_is_not_an_error(self) -> None:
        assert wilson_interval(0, 0).point == 0.0


class TestMcNemar:
    def test_counts_the_four_cells(self) -> None:
        a = [_p("1", "x", "x"), _p("2", "x", "y"), _p("3", "x", "x"), _p("4", "x", "y")]
        b = [_p("1", "x", "x"), _p("2", "x", "x"), _p("3", "x", "y"), _p("4", "x", "y")]
        result = mcnemar(a, b)
        assert (result.both_correct, result.only_a, result.only_b, result.both_wrong) == (
            1,
            1,
            1,
            1,
        )

    def test_a_perfectly_symmetric_disagreement_is_not_significant(self) -> None:
        a = [_p(str(i), "x", "x") for i in range(10)] + [
            _p(str(100 + i), "x", "y") for i in range(10)
        ]
        b = [_p(str(i), "x", "y") for i in range(10)] + [
            _p(str(100 + i), "x", "x") for i in range(10)
        ]
        assert mcnemar(a, b).p_value == 1.0

    def test_a_one_sided_disagreement_is_significant(self) -> None:
        """Ten disagreements all favouring b. Under the null each is a fair
        coin, so p = 2 * 0.5^10 = 1/512."""
        a = [_p(str(i), "x", "y") for i in range(10)]
        b = [_p(str(i), "x", "x") for i in range(10)]
        result = mcnemar(a, b)
        assert result.only_a == 0
        assert result.only_b == 10
        assert result.p_value == pytest.approx(2 * 0.5**10, rel=1e-9)

    def test_agreement_everywhere_yields_no_evidence(self) -> None:
        rows = [_p(str(i), "x", "x") for i in range(50)]
        result = mcnemar(rows, rows)
        assert result.discordant == 0
        assert result.p_value == 1.0

    def test_examples_missing_from_one_side_are_skipped(self) -> None:
        a = [_p("1", "x", "x"), _p("2", "x", "x")]
        b = [_p("1", "x", "x")]
        assert mcnemar(a, b).both_correct == 1


class TestPerClass:
    def test_precision_recall_and_f1(self) -> None:
        # Label "spam": 2 true, 1 found, 1 false alarm.
        rows = [
            _p("1", "spam", "spam"),
            _p("2", "spam", "ham"),
            _p("3", "ham", "spam"),
            _p("4", "ham", "ham"),
        ]
        spam = next(m for m in per_class(rows) if m.label == "spam")
        assert spam.support == 2
        assert spam.predicted == 2
        assert spam.precision == 0.5
        assert spam.recall == 0.5
        assert spam.f1 == 0.5

    def test_prediction_ratio_exposes_overuse(self) -> None:
        rows = [_p("1", "a", "b"), _p("2", "a", "b"), _p("3", "b", "b")]
        by_label = {m.label: m for m in per_class(rows)}
        assert by_label["b"].prediction_ratio == 3.0
        assert by_label["a"].prediction_ratio == 0.0

    def test_a_label_never_predicted_scores_zero_without_dividing_by_zero(self) -> None:
        rows = [_p("1", "a", "b"), _p("2", "b", "b")]
        a = next(m for m in per_class(rows) if m.label == "a")
        assert (a.precision, a.recall, a.f1) == (0.0, 0.0, 0.0)


class TestPriorBias:
    def test_a_faithful_method_shows_no_bias(self) -> None:
        rows = [_p(str(i), "a", "a") for i in range(20)] + [
            _p(str(100 + i), "b", "b") for i in range(20)
        ]
        bias = prior_bias(per_class(rows))
        assert bias.chi_square == 0.0
        assert bias.p_value == 1.0

    def test_a_method_that_always_guesses_one_label_is_flagged(self) -> None:
        rows = [_p(str(i), "a", "b") for i in range(20)] + [
            _p(str(100 + i), "b", "b") for i in range(20)
        ]
        bias = prior_bias(per_class(rows))
        assert bias.most_overused == "b"
        assert bias.most_overused_ratio == 2.0
        assert bias.most_underused == "a"
        assert bias.p_value < 0.001


def test_confusion_pairs_are_ranked_by_frequency() -> None:
    rows = (
        [_p(str(i), "a", "b") for i in range(5)]
        + [_p(str(100 + i), "c", "d") for i in range(2)]
        + [_p("200", "a", "a")]
    )
    assert confusion_pairs(rows)[0] == ("a", "b", 5)


def test_accuracy_by_length_splits_into_buckets() -> None:
    texts = {str(i): "x" * (i + 1) for i in range(20)}
    rows = [_p(str(i), "a", "a" if i < 10 else "b") for i in range(20)]
    strata = accuracy_by_length(rows, texts, buckets=2)
    assert len(strata) == 2
    # Short inputs were all correct, long inputs all wrong.
    assert strata[0][2].point == 1.0
    assert strata[1][2].point == 0.0


def test_paired_bootstrap_recovers_the_observed_difference() -> None:
    a = [_p(str(i), "x", "y") for i in range(100)]
    b = [_p(str(i), "x", "x" if i < 60 else "y") for i in range(100)]
    interval = paired_bootstrap(a, b, iterations=2000)
    assert interval.point == pytest.approx(0.6, abs=1e-9)
    assert interval.low < 0.6 < interval.high


def test_paired_bootstrap_is_reproducible() -> None:
    a = [_p(str(i), "x", "y" if i % 3 else "x") for i in range(80)]
    b = [_p(str(i), "x", "x" if i % 2 else "y") for i in range(80)]
    first = paired_bootstrap(a, b, iterations=1000, seed=7)
    second = paired_bootstrap(a, b, iterations=1000, seed=7)
    assert (first.low, first.high) == (second.low, second.high)


def test_fallback_rate_counts_the_default_answer() -> None:
    rows = [_p("1", "a", "other"), _p("2", "a", "a"), _p("3", "b", "other")]
    assert fallback_rate(rows, "other") == pytest.approx(2 / 3)
    assert fallback_rate([], "other") == 0.0


def test_wilson_is_not_the_normal_approximation() -> None:
    """Guards against someone 'simplifying' this back to p ± z·sqrt(p(1-p)/n),
    whose upper bound here exceeds 1 and is therefore not a probability."""
    successes, trials = 98, 100
    p = successes / trials
    naive_high = p + 1.959963985 * math.sqrt(p * (1 - p) / trials)
    assert naive_high > 1.0
    assert wilson_interval(successes, trials).high <= 1.0
