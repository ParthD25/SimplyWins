"""Persistence access for benchmark problems.

Services depend on the ``ProblemRepository`` protocol, not on SQLAlchemy, so
the storage engine can change without touching business logic.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.benchmark import Problem


class ProblemRepository(Protocol):
    def list_problems(self) -> list[Problem]: ...

    def get_by_slug(self, slug: str) -> Problem | None: ...

    def add(self, problem: Problem) -> None: ...

    def count(self) -> int: ...


class SqlAlchemyProblemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_problems(self) -> list[Problem]:
        # Ordered by title so the listing is stable across requests and engines.
        statement = select(Problem).order_by(Problem.title)
        return list(self._session.scalars(statement))

    def get_by_slug(self, slug: str) -> Problem | None:
        statement = select(Problem).where(Problem.slug == slug)
        return self._session.scalars(statement).one_or_none()

    def add(self, problem: Problem) -> None:
        self._session.add(problem)

    def count(self) -> int:
        return len(list(self._session.scalars(select(Problem.id))))
