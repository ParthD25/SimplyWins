"""The SimplestWins decision rule.

This module is the authoritative implementation of section 3 of
``PROJECT_STANDARD.md``. It is deliberately pure: no I/O, no ORM types, no
framework imports. Everything it needs arrives as arguments so the rule can be
unit-tested in isolation and reasoned about without a database or HTTP layer.

The rule, verbatim from the standard:

1. Evaluate every method on the same benchmark definition and dataset version.
2. Filter to methods satisfying all hard requirements.
3. Sort passing methods by ``complexity_rank`` ascending.
4. Break ties by lower cost, then lower latency.
5. If no method passes, return ``NO_PASSING_METHOD``; do not force a winner.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

# Constraint identifiers. They are part of the API surface (they appear in
# recommendation responses), so they are named constants rather than inline
# strings scattered across the module.
CONSTRAINT_MIN_ACCURACY = "min_accuracy"
CONSTRAINT_MAX_LATENCY_MS = "max_latency_ms"
CONSTRAINT_AUDITABILITY = "auditability_required"

# Cost figures throughout the project are quoted per 1,000 units of work, so a
# monthly projection divides the operating volume by this batch size.
COST_BATCH_SIZE = 1_000


class DataState(StrEnum):
    """Provenance of a figure. Section 5 of PROJECT_STANDARD.md."""

    DEMO = "DEMO"
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"


class RecommendationStatus(StrEnum):
    """Outcome of applying the decision rule."""

    PASSING_METHOD_FOUND = "PASSING_METHOD_FOUND"
    NO_PASSING_METHOD = "NO_PASSING_METHOD"
    # Not every method has been measured, so no winner can be named — an
    # unmeasured method could still change the outcome. Section 3.1.
    BENCHMARK_INCOMPLETE = "BENCHMARK_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class Requirements:
    """The hard operating requirements a method must satisfy.

    ``monthly_volume`` is deliberately *not* a hard constraint. It scales the
    cost projection so a reader can see what a method would cost at their
    operating volume, but no method is excluded on the basis of volume alone.
    """

    min_accuracy: float
    max_latency_ms: float
    auditability_required: bool
    monthly_volume: int


@dataclass(frozen=True, slots=True)
class MethodCandidate:
    """One implementation class competing on a benchmark problem.

    ``result_state`` decides whether this method's numbers may shape the
    outcome. Only ``MEASURED`` figures do; see the evidence rule in section 3.1
    of PROJECT_STANDARD.md.
    """

    method_id: str
    complexity_rank: int
    accuracy: float
    latency_ms: float
    cost_per_1k: float
    deterministic: bool
    auditable: bool
    result_state: DataState = DataState.DEMO

    @property
    def is_evidence(self) -> bool:
        return self.result_state is DataState.MEASURED

    def monthly_cost(self, monthly_volume: int) -> float:
        """Projected monthly spend for this method at ``monthly_volume`` units."""
        return self.cost_per_1k * monthly_volume / COST_BATCH_SIZE


@dataclass(frozen=True, slots=True)
class ConstraintCheck:
    """Whether one method satisfied one hard requirement.

    Retained per method rather than discarded on filtering because the standard
    (section 4) requires runs to record pass/fail against each active
    constraint, and the UI shows a reader *why* a method was excluded.
    """

    constraint: str
    required: float | bool
    actual: float | bool
    passed: bool


@dataclass(frozen=True, slots=True)
class MethodEvaluation:
    """A method's full pass/fail record against the active requirements.

    ``counts_as_evidence`` is false for illustrative figures. Such a method is
    still evaluated and returned so the UI can show the intended comparison
    set, but ``passed`` is never allowed to promote it into the outcome.
    """

    method_id: str
    complexity_rank: int
    passed: bool
    monthly_cost: float
    constraint_checks: tuple[ConstraintCheck, ...]
    result_state: DataState = DataState.DEMO
    counts_as_evidence: bool = False

    @property
    def failed_constraints(self) -> tuple[str, ...]:
        return tuple(check.constraint for check in self.constraint_checks if not check.passed)


@dataclass(frozen=True, slots=True)
class Recommendation:
    """The result of applying the decision rule to a set of methods.

    ``best_measured_method_id`` is a provisional leader among measured methods
    when the benchmark is incomplete. It is deliberately not the recommendation:
    a method still awaiting measurement could displace it.
    """

    status: RecommendationStatus
    recommended_method_id: str | None
    reason: str
    evaluations: tuple[MethodEvaluation, ...]
    passing_method_ids: tuple[str, ...]
    measured_count: int = 0
    method_count: int = 0
    best_measured_method_id: str | None = None


def evaluate_method(method: MethodCandidate, requirements: Requirements) -> MethodEvaluation:
    """Check one method against every hard requirement.

    Auditability is only checked when the caller actually requires it; when it
    is not required the constraint is not active and is omitted rather than
    recorded as a trivial pass.
    """
    checks = [
        ConstraintCheck(
            constraint=CONSTRAINT_MIN_ACCURACY,
            required=requirements.min_accuracy,
            actual=method.accuracy,
            passed=method.accuracy >= requirements.min_accuracy,
        ),
        ConstraintCheck(
            constraint=CONSTRAINT_MAX_LATENCY_MS,
            required=requirements.max_latency_ms,
            actual=method.latency_ms,
            passed=method.latency_ms <= requirements.max_latency_ms,
        ),
    ]
    if requirements.auditability_required:
        checks.append(
            ConstraintCheck(
                constraint=CONSTRAINT_AUDITABILITY,
                required=True,
                actual=method.auditable,
                passed=method.auditable,
            )
        )

    return MethodEvaluation(
        method_id=method.method_id,
        complexity_rank=method.complexity_rank,
        passed=all(check.passed for check in checks),
        monthly_cost=method.monthly_cost(requirements.monthly_volume),
        constraint_checks=tuple(checks),
        result_state=method.result_state,
        counts_as_evidence=method.is_evidence,
    )


def _selection_key(method: MethodCandidate) -> tuple[int, float, float, str]:
    """Ordering used to pick among passing methods.

    Complexity first (the product thesis), then the standard's tie-breaks: lower
    cost, then lower latency. ``method_id`` is the final key purely so that two
    methods identical on every ranked dimension still produce a stable, testable
    result rather than depending on input order.
    """
    return (method.complexity_rank, method.cost_per_1k, method.latency_ms, method.method_id)


def recommend(
    methods: Sequence[MethodCandidate],
    requirements: Requirements,
) -> Recommendation:
    """Apply the SimplestWins decision rule.

    Returns the lowest-complexity method satisfying every hard requirement,
    considering only methods whose results are ``MEASURED``.

    Three outcomes, and two of them name no winner:

    - ``BENCHMARK_INCOMPLETE`` when any method is still unmeasured. An
      unmeasured method could displace the current leader, so recommending one
      would overstate what is known.
    - ``NO_PASSING_METHOD`` when everything is measured but nothing satisfies
      the requirements. The standard forbids nominating a "closest" method.
    - ``PASSING_METHOD_FOUND`` otherwise.
    """
    evaluations = tuple(evaluate_method(method, requirements) for method in methods)

    # The evidence rule (section 3.1): only MEASURED figures may shape the
    # outcome. Illustrative methods are still evaluated and returned so the UI
    # can show the intended comparison set, but they are excluded here.
    measured = [method for method in methods if method.is_evidence]
    measured_count = len(measured)
    method_count = len(methods)

    passing_ids = {
        evaluation.method_id
        for evaluation in evaluations
        if evaluation.passed and evaluation.counts_as_evidence
    }
    ranked = sorted(
        (method for method in measured if method.method_id in passing_ids),
        key=_selection_key,
    )
    passing_method_ids = tuple(method.method_id for method in ranked)
    best_measured = ranked[0].method_id if ranked else None

    # An unmeasured method could still win, so nothing is recommended until the
    # whole set is measured. The provisional leader is reported separately and
    # is explicitly not a recommendation.
    if measured_count < method_count:
        return Recommendation(
            status=RecommendationStatus.BENCHMARK_INCOMPLETE,
            recommended_method_id=None,
            reason=(
                f"Benchmark incomplete: {measured_count} of {method_count} methods "
                "measured. No recommendation is made until every method has been "
                "measured, because an unmeasured method could change the outcome."
            ),
            evaluations=evaluations,
            passing_method_ids=passing_method_ids,
            measured_count=measured_count,
            method_count=method_count,
            best_measured_method_id=best_measured,
        )

    if not ranked:
        return Recommendation(
            status=RecommendationStatus.NO_PASSING_METHOD,
            recommended_method_id=None,
            reason=(
                "No method satisfies every hard requirement. Relax a requirement or "
                "add a method that meets it; no winner is nominated."
            ),
            evaluations=evaluations,
            passing_method_ids=(),
            measured_count=measured_count,
            method_count=method_count,
        )

    winner = ranked[0]
    return Recommendation(
        status=RecommendationStatus.PASSING_METHOD_FOUND,
        recommended_method_id=winner.method_id,
        reason="Lowest-complexity method satisfying every hard constraint.",
        evaluations=evaluations,
        passing_method_ids=passing_method_ids,
        measured_count=measured_count,
        method_count=method_count,
        best_measured_method_id=winner.method_id,
    )
