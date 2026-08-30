"""Unit tests for the decision rule.

These exercise ``app.domain.recommendation`` directly — no database, no HTTP —
because the rule is the part of the product that must never drift.
"""

from __future__ import annotations

import pytest

from app.domain.recommendation import (
    CONSTRAINT_AUDITABILITY,
    CONSTRAINT_MAX_LATENCY_MS,
    CONSTRAINT_MIN_ACCURACY,
    DataState,
    MethodCandidate,
    RecommendationStatus,
    Requirements,
    recommend,
)


def method(
    method_id: str,
    *,
    rank: int,
    accuracy: float,
    latency_ms: int = 100,
    cost_per_1k: float = 1.0,
    auditable: bool = True,
    deterministic: bool = True,
    result_state: DataState = DataState.MEASURED,
) -> MethodCandidate:
    """Defaults to MEASURED so ranking tests exercise ranking.

    Provenance gating is covered separately in TestEvidenceRule. Note the
    production default is DEMO — the rule fails closed.
    """
    return MethodCandidate(
        method_id=method_id,
        complexity_rank=rank,
        accuracy=accuracy,
        latency_ms=latency_ms,
        cost_per_1k=cost_per_1k,
        deterministic=deterministic,
        auditable=auditable,
        result_state=result_state,
    )


def requirements(
    *,
    min_accuracy: float = 90.0,
    max_latency_ms: int = 1000,
    auditability_required: bool = False,
    monthly_volume: int = 100_000,
) -> Requirements:
    return Requirements(
        min_accuracy=min_accuracy,
        max_latency_ms=max_latency_ms,
        auditability_required=auditability_required,
        monthly_volume=monthly_volume,
    )


RULES = method("rules", rank=1, accuracy=96.0, latency_ms=10, cost_per_1k=0.01)
TRADITIONAL_ML = method("ml", rank=2, accuracy=97.0, latency_ms=30, cost_per_1k=0.05)
SMALL_MODEL = method(
    "small",
    rank=3,
    accuracy=98.0,
    latency_ms=200,
    cost_per_1k=0.9,
    auditable=False,
    deterministic=False,
)
FRONTIER = method(
    "frontier",
    rank=4,
    accuracy=99.0,
    latency_ms=900,
    cost_per_1k=7.5,
    auditable=False,
    deterministic=False,
)
ALL_METHODS = (RULES, TRADITIONAL_ML, SMALL_MODEL, FRONTIER)


def test_rules_wins_when_it_is_the_simplest_passing_method() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=95.0))

    assert result.status is RecommendationStatus.PASSING_METHOD_FOUND
    assert result.recommended_method_id == "rules"


def test_more_accurate_method_does_not_displace_a_simpler_passing_one() -> None:
    """The product thesis: extra accuracy is not a reason to add complexity."""
    result = recommend(ALL_METHODS, requirements(min_accuracy=95.0))

    assert result.recommended_method_id == "rules"
    assert result.passing_method_ids[0] == "rules"
    assert set(result.passing_method_ids) == {"rules", "ml", "small", "frontier"}


def test_traditional_ml_wins_when_rules_fail_accuracy() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=96.5))

    assert result.recommended_method_id == "ml"
    assert "rules" not in result.passing_method_ids


def test_small_model_wins_when_simpler_methods_fail_accuracy() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=97.5))

    assert result.recommended_method_id == "small"


def test_auditability_requirement_excludes_non_auditable_methods() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=97.5, auditability_required=True))

    # small and frontier clear the accuracy bar but are not auditable, and no
    # auditable method reaches 97.5, so nothing passes.
    assert result.status is RecommendationStatus.NO_PASSING_METHOD
    assert result.recommended_method_id is None

    small_evaluation = next(e for e in result.evaluations if e.method_id == "small")
    assert CONSTRAINT_AUDITABILITY in small_evaluation.failed_constraints


def test_auditability_requirement_falls_back_to_the_simplest_auditable_method() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=96.5, auditability_required=True))

    assert result.recommended_method_id == "ml"
    assert result.passing_method_ids == ("ml",)


def test_latency_ceiling_excludes_slow_methods() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=97.5, max_latency_ms=150))

    # small (200ms) and frontier (900ms) both exceed the ceiling.
    assert result.status is RecommendationStatus.NO_PASSING_METHOD
    frontier_evaluation = next(e for e in result.evaluations if e.method_id == "frontier")
    assert CONSTRAINT_MAX_LATENCY_MS in frontier_evaluation.failed_constraints


def test_tie_break_prefers_lower_cost_at_equal_complexity() -> None:
    cheap = method("cheap", rank=2, accuracy=95.0, latency_ms=50, cost_per_1k=0.10)
    expensive = method("expensive", rank=2, accuracy=99.0, latency_ms=10, cost_per_1k=5.00)

    result = recommend((expensive, cheap), requirements(min_accuracy=90.0))

    assert result.recommended_method_id == "cheap"


def test_tie_break_falls_through_to_latency_at_equal_cost() -> None:
    fast = method("fast", rank=2, accuracy=95.0, latency_ms=20, cost_per_1k=0.25)
    slow = method("slow", rank=2, accuracy=99.0, latency_ms=400, cost_per_1k=0.25)

    result = recommend((slow, fast), requirements(min_accuracy=90.0))

    assert result.recommended_method_id == "fast"


def test_impossible_requirements_return_no_passing_method() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=99.9))

    assert result.status is RecommendationStatus.NO_PASSING_METHOD
    assert result.recommended_method_id is None
    assert result.passing_method_ids == ()


def test_no_passing_method_never_nominates_a_closest_option() -> None:
    """Section 2 of the standard: do not declare a winner when none passes."""
    result = recommend(ALL_METHODS, requirements(min_accuracy=100.0, max_latency_ms=1))

    assert result.recommended_method_id is None
    assert not any(evaluation.passed for evaluation in result.evaluations)


def test_every_method_is_evaluated_even_when_it_fails() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=99.9))

    assert {e.method_id for e in result.evaluations} == {m.method_id for m in ALL_METHODS}


def test_accuracy_constraint_is_inclusive_at_the_threshold() -> None:
    exact = method("exact", rank=1, accuracy=95.0)

    result = recommend((exact,), requirements(min_accuracy=95.0))

    assert result.recommended_method_id == "exact"


def test_latency_constraint_is_inclusive_at_the_threshold() -> None:
    exact = method("exact", rank=1, accuracy=99.0, latency_ms=500)

    result = recommend((exact,), requirements(min_accuracy=90.0, max_latency_ms=500))

    assert result.recommended_method_id == "exact"


def test_auditability_constraint_is_omitted_when_not_required() -> None:
    result = recommend((SMALL_MODEL,), requirements(min_accuracy=90.0))

    checks = {check.constraint for check in result.evaluations[0].constraint_checks}
    assert checks == {CONSTRAINT_MIN_ACCURACY, CONSTRAINT_MAX_LATENCY_MS}


def test_monthly_volume_scales_cost_but_never_excludes_a_method() -> None:
    result = recommend(ALL_METHODS, requirements(min_accuracy=95.0, monthly_volume=1_000_000))

    frontier_evaluation = next(e for e in result.evaluations if e.method_id == "frontier")
    assert frontier_evaluation.monthly_cost == pytest.approx(7500.0)
    assert frontier_evaluation.passed


def test_empty_method_set_returns_no_passing_method() -> None:
    result = recommend((), requirements())

    assert result.status is RecommendationStatus.NO_PASSING_METHOD
    assert result.evaluations == ()


def test_result_is_independent_of_input_order() -> None:
    forward = recommend(ALL_METHODS, requirements(min_accuracy=95.0))
    reversed_order = recommend(tuple(reversed(ALL_METHODS)), requirements(min_accuracy=95.0))

    assert forward.recommended_method_id == reversed_order.recommended_method_id
    assert forward.passing_method_ids == reversed_order.passing_method_ids


class TestEvidenceRule:
    """Section 3.1: only MEASURED figures may shape a recommendation.

    This is the load-bearing rule of the product. If it is ever weakened, these
    tests are the thing that should stop it.
    """

    def test_demo_is_the_default_so_the_rule_fails_closed(self) -> None:
        """A caller who forgets to set provenance gets no recommendation, never
        an accidental one."""
        candidate = MethodCandidate(
            method_id="unspecified",
            complexity_rank=1,
            accuracy=99.0,
            latency_ms=10,
            cost_per_1k=0.01,
            deterministic=True,
            auditable=True,
        )

        assert candidate.result_state is DataState.DEMO
        assert candidate.is_evidence is False
        assert recommend((candidate,), requirements()).recommended_method_id is None

    def test_mixed_states_produce_no_recommendation(self) -> None:
        result = recommend(
            (
                method("rules", rank=1, accuracy=96.0),
                method("llm", rank=4, accuracy=99.0, result_state=DataState.DEMO),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.status is RecommendationStatus.BENCHMARK_INCOMPLETE
        assert result.recommended_method_id is None

    def test_incomplete_status_reports_how_much_evidence_exists(self) -> None:
        result = recommend(
            (
                method("a", rank=1, accuracy=96.0),
                method("b", rank=2, accuracy=97.0, result_state=DataState.DEMO),
                method("c", rank=3, accuracy=98.0, result_state=DataState.DEMO),
                method("d", rank=4, accuracy=99.0, result_state=DataState.DEMO),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.measured_count == 1
        assert result.method_count == 4
        assert "1 of 4" in result.reason

    def test_a_demo_method_never_wins_even_when_it_would_rank_first(self) -> None:
        """The exact failure the rule exists to prevent: an illustrative figure
        beating a measured one."""
        result = recommend(
            (
                method("demo-simplest", rank=1, accuracy=99.9, result_state=DataState.DEMO),
                method("measured", rank=2, accuracy=96.0),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.recommended_method_id is None
        assert result.best_measured_method_id == "measured"
        assert "demo-simplest" not in result.passing_method_ids

    def test_demo_methods_are_excluded_from_the_passing_set(self) -> None:
        result = recommend(
            (
                method("measured", rank=1, accuracy=96.0),
                method("demo", rank=2, accuracy=99.0, result_state=DataState.DEMO),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.passing_method_ids == ("measured",)

    def test_demo_methods_are_still_evaluated_and_returned(self) -> None:
        """They are shown for context; they are simply not evidence."""
        result = recommend(
            (
                method("measured", rank=1, accuracy=96.0),
                method("demo", rank=2, accuracy=99.0, result_state=DataState.DEMO),
            ),
            requirements(min_accuracy=95.0),
        )

        by_id = {item.method_id: item for item in result.evaluations}
        assert set(by_id) == {"measured", "demo"}
        assert by_id["demo"].passed is True
        assert by_id["demo"].counts_as_evidence is False
        assert by_id["measured"].counts_as_evidence is True

    def test_best_measured_is_offered_while_incomplete(self) -> None:
        result = recommend(
            (
                method("cheap", rank=1, accuracy=96.0, cost_per_1k=0.01),
                method("pending", rank=2, accuracy=99.0, result_state=DataState.DEMO),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.status is RecommendationStatus.BENCHMARK_INCOMPLETE
        assert result.best_measured_method_id == "cheap"
        assert result.recommended_method_id is None, "provisional leader is not a winner"

    def test_no_best_measured_when_no_measured_method_passes(self) -> None:
        result = recommend(
            (
                method("weak", rank=1, accuracy=80.0),
                method("demo", rank=2, accuracy=99.0, result_state=DataState.DEMO),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.best_measured_method_id is None

    def test_fully_measured_set_recommends_normally(self) -> None:
        result = recommend(
            (
                method("rules", rank=1, accuracy=96.0),
                method("ml", rank=2, accuracy=99.0),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.status is RecommendationStatus.PASSING_METHOD_FOUND
        assert result.recommended_method_id == "rules"
        assert result.measured_count == result.method_count == 2

    def test_fully_measured_but_nothing_passes_is_still_no_passing_method(self) -> None:
        """Incompleteness must not mask a genuine no-pass answer."""
        result = recommend(
            (
                method("rules", rank=1, accuracy=80.0),
                method("ml", rank=2, accuracy=85.0),
            ),
            requirements(min_accuracy=95.0),
        )

        assert result.status is RecommendationStatus.NO_PASSING_METHOD
        assert result.recommended_method_id is None

    def test_estimated_is_not_evidence_either(self) -> None:
        result = recommend(
            (method("est", rank=1, accuracy=99.0, result_state=DataState.ESTIMATED),),
            requirements(min_accuracy=95.0),
        )

        assert result.status is RecommendationStatus.BENCHMARK_INCOMPLETE
        assert result.recommended_method_id is None
