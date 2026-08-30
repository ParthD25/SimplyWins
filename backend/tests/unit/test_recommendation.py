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
) -> MethodCandidate:
    return MethodCandidate(
        method_id=method_id,
        complexity_rank=rank,
        accuracy=accuracy,
        latency_ms=latency_ms,
        cost_per_1k=cost_per_1k,
        deterministic=deterministic,
        auditable=auditable,
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
