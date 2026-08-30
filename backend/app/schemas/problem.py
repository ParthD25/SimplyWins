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
    max_latency_ms: int = Field(gt=0, description="Latency ceiling in milliseconds.")
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
    """One method's measured or illustrative performance on a problem."""

    result_state: DataState
    accuracy: float = Field(ge=0, le=100)
    latency_p50_ms: int = Field(ge=0)
    cost_per_1k: float = Field(ge=0, description="Cost in USD per 1,000 units of work.")
    deterministic: bool
    auditable: bool
    metric_definition_version: str
    raw_artifact_uri: str | None = None
    measured_at: str | None = None


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
