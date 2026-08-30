"""Problem, method, and result payloads returned by /v1/problems."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema, DataState, MethodClass


class RequirementsPayload(ApiSchema):
    """Hard operating requirements, plus the volume used for cost projection.

    ``monthly_volume`` scales the cost projection only. It never excludes a
    method, so it is not validated as a constraint threshold.
    """

    min_accuracy: float = Field(ge=0, le=100, description="Minimum accuracy percentage.")
    max_latency_ms: float = Field(gt=0, description="Latency ceiling in milliseconds.")
    auditability_required: bool = Field(
        description="When true, only auditable methods are eligible."
    )
    monthly_volume: int = Field(ge=0, description="Operating volume used to project cost.")


class DatasetPayload(ApiSchema):
    """Dataset provenance. Nullable fields are the ones a DEMO problem cannot fill."""

    name: str
    version: str
    sample_count_label: str
    sha256: str | None = None
    license: str | None = None
    source_url: str | None = None
    provenance_notes: str


class ResultPayload(ApiSchema):
    """One method's measured or illustrative performance on a problem.

    ``cost_state`` is separate from ``result_state`` because cost is projected
    from measured latency plus a dated rate assumption. A method can therefore
    be MEASURED on quality while its cost is only ESTIMATED.
    """

    result_state: DataState
    accuracy: float = Field(ge=0, le=100)
    latency_p50_ms: float = Field(
        ge=0, description="Median latency in ms; sub-millisecond values are real."
    )
    cost_per_1k: float = Field(ge=0, description="Cost in USD per 1,000 units of work.")
    deterministic: bool
    auditable: bool
    metric_definition_version: str
    raw_artifact_uri: str | None = None
    measured_at: str | None = None
    cost_state: DataState = DataState.DEMO
    run_id: str | None = Field(
        default=None, description="Benchmark run that produced a MEASURED result."
    )
    sample_count: int | None = Field(
        default=None, description="Examples the measured result was scored over."
    )


class MethodPayload(ApiSchema):
    method_id: str
    name: str
    short_name: str
    method_class: MethodClass
    complexity_rank: int = Field(ge=1)
    implementation_version: str
    provider: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    notes: str
    result: ResultPayload


class ProblemSummary(ApiSchema):
    """Listing shape for /v1/problems. Omits methods to keep the list light."""

    slug: str
    title: str
    category: str
    description: str
    decision_question: str
    status: DataState
    benchmark_definition_version: str


class ProblemDetail(ProblemSummary):
    """Full shape for /v1/problems/{slug}."""

    rationale: str
    dataset: DatasetPayload
    default_requirements: RequirementsPayload
    methods: tuple[MethodPayload, ...]


class ProblemListResponse(ApiSchema):
    problems: tuple[ProblemSummary, ...]
    count: int
