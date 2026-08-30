"""Database engine and session wiring.

SQLite is the local development database (Phase 2). The engine URL is the only
thing that changes to move to PostgreSQL, which is why nothing outside this
module constructs a connection.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _connect_args(database_url: str) -> dict[str, object]:
    # SQLite guards connections against cross-thread use; FastAPI's threadpool
    # legitimately hands a session to a worker thread, so the check is relaxed
    # for SQLite only.
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, connect_args=_connect_args(url), future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def create_all() -> None:
    """Create tables. Adequate for SQLite in this phase; Alembic arrives with
    the first schema change that has to preserve existing rows."""
    Base.metadata.create_all(bind=get_engine())


def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_state() -> None:
    """Drop cached engine/session factory. Used by tests that repoint the URL."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
