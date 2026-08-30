"""FastAPI dependencies.

Routes depend on the repository protocol, not on a session, so swapping the
persistence layer does not touch the transport layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import session_scope
from app.repositories.problem_repository import (
    ProblemRepository,
    SqlAlchemyProblemRepository,
)


def get_session() -> Iterator[Session]:
    yield from session_scope()


def get_problem_repository(
    session: Annotated[Session, Depends(get_session)],
) -> ProblemRepository:
    return SqlAlchemyProblemRepository(session)


ProblemRepositoryDep = Annotated[ProblemRepository, Depends(get_problem_repository)]
