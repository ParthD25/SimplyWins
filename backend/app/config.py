"""Application settings.

Secrets and environment-specific values arrive through environment variables
only (section 8 of PROJECT_STANDARD.md). This phase needs no secrets at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# The seed directory is versioned so a definition change ships as a new
# directory rather than a silent edit to the current one.
DEFAULT_SEED_VERSION = "v1"
DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./simplestwins.db"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    seed_version: str
    cors_allow_origins: tuple[str, ...]
    log_level: str


def _split_origins(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("SIMPLESTWINS_DATABASE_URL", DEFAULT_DATABASE_URL),
        seed_version=os.getenv("SIMPLESTWINS_SEED_VERSION", DEFAULT_SEED_VERSION),
        # Defaults cover a local static-frontend server; deployments set this
        # explicitly rather than relying on a wildcard.
        cors_allow_origins=_split_origins(
            os.getenv(
                "SIMPLESTWINS_CORS_ORIGINS",
                "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173",
            )
        ),
        log_level=os.getenv("SIMPLESTWINS_LOG_LEVEL", "INFO"),
    )
