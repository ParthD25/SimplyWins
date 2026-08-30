"""Shared fixtures.

Each test module gets its own SQLite file so seeding in one test cannot leak
into another.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings


@pytest.fixture
def temp_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("SIMPLESTWINS_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path}/test.db")
    get_settings.cache_clear()
    db.reset_state()
    yield
    db.reset_state()
    get_settings.cache_clear()


@pytest.fixture
def client(temp_database: None) -> Iterator[TestClient]:
    from app.main import create_app

    # The context manager runs lifespan, which creates tables and seeds.
    with TestClient(create_app()) as test_client:
        yield test_client
