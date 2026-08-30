"""Problem, method, and result payloads returned by /v1/problems."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema, DataState, MethodClass, ProblemStatus


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
    sample_count_label: str | None = None
    sha256: str | None = None
    license: str | None = None
    source_url: str | None = None
    provenance_notes: str | None = None


class TermProvenancePayload(ApiSchema):
    """How a keyword method's vocabulary divides against its training corpus.

    Published because a rules baseline whose every term is drawn from the data
    it is scored on is a fitted model wearing the word "rules". Comparing the
    two halves is what caught this benchmark measuring its own author when the
    corpus was synthetic.
    """

    total_terms: int
    attested_terms: int
    unattested_terms: int
    attested_fraction: float
    accuracy_all_terms: float
    accuracy_attested_only: float
    accuracy_unattested_only: float


class LeakageAuditPayload(ApiSchema):
    """Whether a result could have come out low.

    An accuracy figure is only evidence if the experiment was capable of
    producing a bad one, so every measured result carries the floors it had to
    beat and a contamination check alongside it.
    """

    majority_label: str
    majority_baseline_accuracy: float
    chance_accuracy: float
    train_size: int
    test_size: int
    contaminated_examples: int
    contamination_rate: float
    term_provenance: TermProvenancePayload | None = None
    notes: list[str] = Field(default_factory=list)


class ResultPayload(ApiSchema):
    """One method's performance on a problem, or the absence of one.

    ``cost_state`` is separate from ``result_state`` because cost is usually
    projected from measured latency plus a dated rate assumption. A method can
    therefore be MEASURED on quality while its cost is only ESTIMATED; a hosted
    model, which reports the tokens it used, is MEASURED on both.

    A ``NOT_RUN`` result carries zeroes in every numeric field. They are
    placeholders, never values: the method is listed because it belongs to the
    comparison set and its absence is what keeps the benchmark incomplete.
    """

    result_state: DataState
    accuracy: float = Field(ge=0, le=100)
    latency_p50_ms: float = Field(
        ge=0, description="Median latency in ms; sub-millisecond values are real."
    )
    cost_per_1k: float = Field(ge=0, description="Cost in USD per 1,000 units of work.")
    deterministic: bool
    auditable: bool
    # Absent for a NOT_RUN method: there is no metric because nothing was
    # measured. Required in practice for every other state.
    metric_definition_version: str | None = None
    raw_artifact_uri: str | None = None
    measured_at: str | None = None
    cost_state: DataState = DataState.DEMO
    run_id: str | None = Field(
        default=None, description="Benchmark run that produced a MEASURED result."
    )
    sample_count: int | None = Field(
        default=None, description="Examples the measured result was scored over."
    )
    leakage_audit: LeakageAuditPayload | None = Field(
        default=None,
        description="Floors and contamination checks the result must be read against.",
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
    """Listing shape for /v1/problems.

    Omits the methods themselves but carries the evidence counts, so a listing
    can show how far a benchmark has got without fetching every problem in
    full — the difference between one request and one per problem.
    """

    slug: str
    title: str
    category: str
    description: str
    decision_question: str
    status: ProblemStatus
    benchmark_definition_version: str
    measured_count: int = Field(description="Methods carrying a MEASURED result.")
    method_count: int = Field(description="Methods in the declared comparison set.")


class ProblemDetail(ProblemSummary):
    """Full shape for /v1/problems/{slug}."""

    rationale: str
    dataset: DatasetPayload
    default_requirements: RequirementsPayload
    methods: tuple[MethodPayload, ...]


class ProblemListResponse(ApiSchema):
    problems: tuple[ProblemSummary, ...]
    count: int
