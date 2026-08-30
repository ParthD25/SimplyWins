"""The recommendation endpoint.

This handler deliberately does nothing but delegate: the decision rule is a
pure function in ``app.domain.recommendation`` and must stay testable without
FastAPI.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ProblemRepositoryDep
from app.api.v1.problems import SlugPath
from app.schemas.common import ErrorResponse
from app.schemas.recommendation import RecommendRequest, RecommendResponse
from app.services import recommendation_service

router = APIRouter(prefix="/problems", tags=["recommendations"])


@router.post(
    "/{slug}/recommend",
    response_model=RecommendResponse,
    summary="Recommend the lowest-complexity method meeting the requirements",
    responses={404: {"model": ErrorResponse, "description": "Unknown problem slug"}},
)
def recommend(
    slug: SlugPath,
    payload: RecommendRequest,
    repository: ProblemRepositoryDep,
) -> RecommendResponse:
    return recommendation_service.recommend_for_problem(repository, slug, payload.requirements)
