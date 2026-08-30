"""Application errors and the single API error envelope.

Section 6 of PROJECT_STANDARD.md requires every error response to be shaped
``{"error": {"code", "message", "details"}}``. The handlers here are the only
place that shape is produced, so no route can accidentally emit a different one.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

# Spelled out rather than taken from `status`, whose constant for this code was
# renamed across Starlette versions.
HTTP_422_UNPROCESSABLE_CONTENT = 422


class ApiError(Exception):
    """Base for errors that map onto the standard envelope."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProblemNotFoundError(ApiError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "problem_not_found"


def _envelope(code: str, message: str, details: dict[str, Any], status_code: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.code, exc.message, exc.details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(
            "validation_error",
            "The request payload failed validation.",
            {"errors": exc.errors()},
            HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(
            "http_error",
            str(exc.detail),
            {},
            exc.status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # The message is deliberately generic; the detail goes to the log, not
        # to the client.
        logger.exception("Unhandled exception", extra={"error_type": type(exc).__name__})
        return _envelope(
            "internal_error",
            "An unexpected error occurred.",
            {},
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
