"""Seeding behaviour."""

from __future__ import annotations

from app.config import get_settings
from app.db import create_all, get_session_factory
from app.repositories.problem_repository import SqlAlchemyProblemRepository
from app.seed.loader import seed_problems


def test_seeding_is_idempotent(temp_database: None) -> None:
    """Restarting the app must not duplicate or overwrite stored definitions."""
    create_all()
    version = get_settings().seed_version

    with get_session_factory()() as session:
        repository = SqlAlchemyProblemRepository(session)
        first = seed_problems(repository, version)
        session.commit()

    with get_session_factory()() as session:
        repository = SqlAlchemyProblemRepository(session)
        second = seed_problems(repository, version)
        session.commit()
        total = repository.count()

    assert first == 3
    assert second == 0
    assert total == 3


def test_seeded_problem_round_trips_through_the_repository(temp_database: None) -> None:
    create_all()
    with get_session_factory()() as session:
        repository = SqlAlchemyProblemRepository(session)
        seed_problems(repository, get_settings().seed_version)
        session.commit()

        problem = repository.get_by_slug("spam-detection")
        assert problem is not None
        assert problem.title == "Spam Detection"
        assert len(problem.methods) == 4
        assert len(problem.dataset_versions) == 1
        assert len(problem.requirement_profiles) == 1
        assert all(method.result is not None for method in problem.methods)


def test_unknown_slug_lookup_returns_none(temp_database: None) -> None:
    create_all()
    with get_session_factory()() as session:
        assert SqlAlchemyProblemRepository(session).get_by_slug("nope") is None
