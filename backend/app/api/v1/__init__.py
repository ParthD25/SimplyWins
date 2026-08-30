"""Version 1 of the public API.

Breaking changes to these shapes require a /v2 router rather than an edit here
(section 6 of PROJECT_STANDARD.md).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import problems, recommendations

router = APIRouter(prefix="/v1")
router.include_router(problems.router)
router.include_router(recommendations.router)
