"""Migrations must stay in step with the models.

`create_all` builds the schema for local development and tests, while a
deployment runs `alembic upgrade head`. Those two paths must produce the same
schema — otherwise a column added to a model reaches production only in
development. These tests are the guard.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["alembic", *command],
        cwd=BACKEND_ROOT,
        env={
            "PATH": str(BACKEND_ROOT / ".venv" / "bin") + ":/usr/bin:/bin",
            "SIMPLESTWINS_DATABASE_URL": database_url,
        },
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def migrated(tmp_path: Path) -> str:
    url = f"sqlite+pysqlite:///{tmp_path}/migrated.db"
    result = _alembic(["upgrade", "head"], url)
    assert result.returncode == 0, result.stderr
    return url


def test_migrations_apply_cleanly(migrated: str) -> None:
    tables = set(inspect(create_engine(migrated)).get_table_names())

    assert {"problem", "method", "result", "dataset_version"} <= tables


def test_no_model_change_is_missing_a_migration(migrated: str) -> None:
    """`alembic check` fails if a model has drifted from the migrations, which
    is how a column silently reaches development but never production."""
    result = _alembic(["check"], migrated)

    assert result.returncode == 0, (
        "Models and migrations have diverged. Run:\n"
        "  alembic revision --autogenerate -m '<what changed>'\n\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_migrations_reverse(migrated: str) -> None:
    """A migration that cannot be undone is a migration that cannot be
    rolled back in an incident."""
    result = _alembic(["downgrade", "base"], migrated)
    assert result.returncode == 0, result.stderr

    tables = set(inspect(create_engine(migrated)).get_table_names())
    assert "problem" not in tables


def test_create_all_and_migrations_agree(migrated: str, tmp_path: Path) -> None:
    """The two schema paths must produce the same tables and columns."""
    # Importing the models module is what registers the tables on the
    # metadata; importing Base alone yields an empty schema.
    from app.models import benchmark  # noqa: F401
    from app.models.base import Base

    direct_url = f"sqlite+pysqlite:///{tmp_path}/direct.db"
    direct_engine = create_engine(direct_url)
    Base.metadata.create_all(direct_engine)

    migrated_inspector = inspect(create_engine(migrated))
    direct_inspector = inspect(direct_engine)

    migrated_tables = set(migrated_inspector.get_table_names()) - {"alembic_version"}
    assert migrated_tables == set(direct_inspector.get_table_names())

    for table in sorted(migrated_tables):
        migrated_columns = {c["name"] for c in migrated_inspector.get_columns(table)}
        direct_columns = {c["name"] for c in direct_inspector.get_columns(table)}
        assert migrated_columns == direct_columns, table
