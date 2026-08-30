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
DEFAULT_SEED_VERSION = "v2"
DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./simplestwins.db"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    seed_version: str
    cors_allow_origins: tuple[str, ...]
    log_level: str
    rate_limit_enabled: bool
    rate_limit_burst: int
    rate_limit_per_second: float
    # Only set this when a proxy in front of the API overwrites
    # X-Forwarded-For. If it is on and nothing sets that header, any client can
    # choose its own rate-limit bucket, which removes the limit entirely.
    rate_limit_trust_forwarded_for: bool


def _split_origins(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
        # Defaults are generous for a read-only API whose pages fetch a handful
        # of documents: they stop one client hammering the service without
        # tripping on ordinary browsing.
        rate_limit_enabled=_flag("SIMPLESTWINS_RATE_LIMIT_ENABLED", True),
        rate_limit_burst=int(os.getenv("SIMPLESTWINS_RATE_LIMIT_BURST", "60")),
        rate_limit_per_second=float(os.getenv("SIMPLESTWINS_RATE_LIMIT_PER_SECOND", "5")),
        rate_limit_trust_forwarded_for=_flag("SIMPLESTWINS_RATE_LIMIT_TRUST_FORWARDED_FOR", False),
    )
