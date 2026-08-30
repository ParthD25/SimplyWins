"""Applies the decision rule to a stored problem.

The rule itself lives in ``app.domain.recommendation`` and knows nothing about
storage or HTTP. This module's only job is translation: ORM rows in, domain
values through, API payload out.
"""

from __future__ import annotations

from app.domain.recommendation import (
    MethodCandidate,
    Recommendation,
    Requirements,
    recommend,
)
from app.models.benchmark import Problem as ProblemModel
from app.repositories.problem_repository import ProblemRepository
from app.schemas.problem import RequirementsPayload
from app.schemas.recommendation import (
    ConstraintCheckPayload,
    MethodEvaluationPayload,
    RecommendResponse,
)
from app.services.problem_service import get_problem_model

DEMO_NOTICE = (
    "These figures are DEMO data, not measured benchmark results. "
    "They illustrate the decision rule and must not be cited as evidence."
)
MEASURED_NOTICE = (
    "Figures include measured results. Check each method's result_state and run provenance."
)


def _to_candidates(problem: ProblemModel) -> tuple[MethodCandidate, ...]:
    candidates = []
    for method in problem.methods:
        result = method.result
        if result is None:
            # A method with no result has nothing to evaluate; excluding it is
            # safer than assuming a figure on its behalf.
            continue
        candidates.append(
            MethodCandidate(
                method_id=method.stable_key,
                complexity_rank=method.complexity_rank,
                accuracy=result.accuracy,
                latency_ms=result.latency_p50_ms,
                cost_per_1k=result.cost_per_1k,
                deterministic=result.deterministic,
                auditable=result.auditable,
            )
        )
    return tuple(candidates)


def _data_state_notice(problem: ProblemModel) -> str:
    states = {method.result.result_state for method in problem.methods if method.result}
    return DEMO_NOTICE if states == {"DEMO"} else MEASURED_NOTICE


def _to_response(problem: ProblemModel, recommendation: Recommendation) -> RecommendResponse:
    evaluations = tuple(
        MethodEvaluationPayload(
            method_id=evaluation.method_id,
            complexity_rank=evaluation.complexity_rank,
            passed=evaluation.passed,
            projected_monthly_cost=round(evaluation.monthly_cost, 2),
            failed_constraints=evaluation.failed_constraints,
            constraint_checks=tuple(
                ConstraintCheckPayload(
                    constraint=check.constraint,
                    required=check.required,
                    actual=check.actual,
                    passed=check.passed,
                )
                for check in evaluation.constraint_checks
            ),
        )
        for evaluation in sorted(recommendation.evaluations, key=lambda e: e.complexity_rank)
    )
    return RecommendResponse(
        status=recommendation.status,
        recommended_method_id=recommendation.recommended_method_id,
        reason=recommendation.reason,
        passing_method_ids=recommendation.passing_method_ids,
        evaluations=evaluations,
        benchmark_definition_version=problem.benchmark_definition_version,
        data_state_notice=_data_state_notice(problem),
    )


def recommend_for_problem(
    repository: ProblemRepository,
    slug: str,
    requirements: RequirementsPayload,
) -> RecommendResponse:
    problem = get_problem_model(repository, slug)
    recommendation = recommend(
        _to_candidates(problem),
        Requirements(
            min_accuracy=requirements.min_accuracy,
            max_latency_ms=requirements.max_latency_ms,
            auditability_required=requirements.auditability_required,
            monthly_volume=requirements.monthly_volume,
        ),
    )
    return _to_response(problem, recommendation)
