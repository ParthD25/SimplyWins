"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.config import get_settings
from app.db import create_all, get_session_factory
from app.errors import register_exception_handlers
from app.logging_config import configure_logging
from app.repositories.problem_repository import SqlAlchemyProblemRepository
from app.schemas.common import ApiSchema
from app.seed.loader import seed_problems

logger = logging.getLogger(__name__)

API_TITLE = "SimplestWins API"
# Application release version. The /v1 path prefix is the contract version and
# changes only on a breaking schema change.
API_VERSION = "0.6.1"


class HealthResponse(ApiSchema):
    status: str
    api_version: str
    problems_loaded: int


def bootstrap() -> int:
    """Create tables and apply seed definitions. Returns the problem count."""
    create_all()
    with get_session_factory()() as session:
        repository = SqlAlchemyProblemRepository(session)
        seed_problems(repository, get_settings().seed_version)
        session.commit()
        return repository.count()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    count = bootstrap()
    logger.info("Application ready", extra={"problems_loaded": count})
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=(
            "Compares implementation classes on the same task and recommends the "
            "lowest-complexity method that satisfies the operating requirements."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_exception_handlers(app)
    app.include_router(v1_router)

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        with get_session_factory()() as session:
            count = SqlAlchemyProblemRepository(session).count()
        return HealthResponse(status="ok", api_version=API_VERSION, problems_loaded=count)

    return app


app = create_app()
