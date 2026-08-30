"""Shared enumerations and the API error envelope."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DataState(StrEnum):
    """Section 5 of PROJECT_STANDARD.md. Every result carries one of these."""

    DEMO = "DEMO"
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    # Listed in the comparison set but never run, so it carries no figures at
    # all. Distinct from DEMO, which carries illustrative ones. Still counted
    # in the method total: the evidence rule turns on every method having been
    # measured, and an unrun method could displace the current leader.
    NOT_RUN = "NOT_RUN"


class ProblemStatus(StrEnum):
    """How far a benchmark problem has got.

    Separate from ``DataState`` because a problem's progress is not a figure's
    provenance: MIXED is meaningless for one number and exactly right for a
    comparison set where some methods have run and others have not.
    """

    MEASURED = "MEASURED"
    PARTIAL = "PARTIAL"
    NOT_RUN = "NOT_RUN"


class MethodClass(StrEnum):
    """Implementation classes compared on a benchmark problem.

    The order here mirrors the default complexity order in section 3 of the
    standard, but ``complexity_rank`` on the method is what the decision rule
    reads; a benchmark may override the ranking with a stored rationale.
    """

    RULES = "rules"
    TRADITIONAL_ML = "traditional-ml"
    SMALL_MODEL = "small-model"
    FRONTIER_LLM = "frontier-llm"


class ApiSchema(BaseModel):
    """Base for every payload the API emits or accepts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ErrorDetail(ApiSchema):
    code: str = Field(description="Stable, machine-readable error code.")
    message: str = Field(description="Human-readable explanation.")
    details: dict[str, object] = Field(
        default_factory=dict, description="Structured context for the error."
    )


class ErrorResponse(ApiSchema):
    """The single error envelope required by section 6 of the standard."""

    error: ErrorDetail
