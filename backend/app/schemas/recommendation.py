"""Request and response payloads for /v1/problems/{slug}/recommend."""

from __future__ import annotations

from pydantic import Field

from app.domain.recommendation import RecommendationStatus
from app.schemas.common import ApiSchema
from app.schemas.problem import RequirementsPayload


class RecommendRequest(ApiSchema):
    requirements: RequirementsPayload


class ConstraintCheckPayload(ApiSchema):
    constraint: str
    required: float | bool
    actual: float | bool
    passed: bool


class MethodEvaluationPayload(ApiSchema):
    """Why a method did or did not qualify, and what it would cost.

    Returned for every method, passing or not, because a reader deciding
    between approaches needs to see which requirement excluded an option.
    """

    method_id: str
    complexity_rank: int
    passed: bool
    projected_monthly_cost: float
    failed_constraints: tuple[str, ...]
    constraint_checks: tuple[ConstraintCheckPayload, ...]


class RecommendResponse(ApiSchema):
    status: RecommendationStatus
    recommended_method_id: str | None = Field(
        default=None,
        description="Null when status is NO_PASSING_METHOD; no winner is forced.",
    )
    reason: str
    passing_method_ids: tuple[str, ...]
    evaluations: tuple[MethodEvaluationPayload, ...]
    benchmark_definition_version: str
    data_state_notice: str
