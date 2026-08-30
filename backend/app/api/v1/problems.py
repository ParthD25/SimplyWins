"""Problem listing and detail endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import ProblemRepositoryDep
from app.schemas.common import ErrorResponse
from app.schemas.problem import ProblemDetail, ProblemListResponse
from app.services import problem_service

router = APIRouter(prefix="/problems", tags=["problems"])

SlugPath = Annotated[
    str,
    Path(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Lowercase-kebab-case problem slug.",
    ),
]


@router.get("", response_model=ProblemListResponse, summary="List benchmark problems")
def list_problems(repository: ProblemRepositoryDep) -> ProblemListResponse:
    problems = problem_service.list_problems(repository)
    return ProblemListResponse(problems=problems, count=len(problems))


@router.get(
    "/{slug}",
    response_model=ProblemDetail,
    summary="Get one benchmark problem",
    responses={404: {"model": ErrorResponse, "description": "Unknown problem slug"}},
)
def get_problem(slug: SlugPath, repository: ProblemRepositoryDep) -> ProblemDetail:
    return problem_service.get_problem_detail(repository, slug)
