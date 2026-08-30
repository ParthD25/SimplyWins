"""Business logic for reading problem definitions.

Route handlers call into this module; they contain no logic of their own. This
is also the only place ORM entities are translated into API schemas, so the
public contract cannot drift with a column rename.
"""

from __future__ import annotations

from app.errors import ProblemNotFoundError
from app.models.benchmark import Method as MethodModel
from app.models.benchmark import Problem as ProblemModel
from app.repositories.problem_repository import ProblemRepository
from app.schemas.common import DataState, MethodClass
from app.schemas.problem import (
    DatasetPayload,
    MethodPayload,
    ProblemDetail,
    ProblemSummary,
    RequirementsPayload,
    ResultPayload,
)
from app.seed.loader import DEFAULT_PROFILE_NAME


def _to_summary(problem: ProblemModel) -> ProblemSummary:
    measured = sum(
        1
        for method in problem.methods
        if method.result is not None and method.result.result_state == DataState.MEASURED
    )
    return ProblemSummary(
        slug=problem.slug,
        title=problem.title,
        category=problem.category,
        description=problem.description,
        decision_question=problem.decision_question,
        status=DataState(problem.status),
        benchmark_definition_version=problem.benchmark_definition_version,
        measured_count=measured,
        method_count=len(problem.methods),
    )


def _to_method_payload(method: MethodModel) -> MethodPayload:
    result = method.result
    if result is None:
        raise ValueError(f"Method {method.stable_key!r} has no stored result")
    return MethodPayload(
        method_id=method.stable_key,
        name=method.name,
        short_name=method.short_name,
        method_class=MethodClass(method.method_class),
        complexity_rank=method.complexity_rank,
        implementation_version=method.implementation_version,
        provider=method.provider,
        model_name=method.model_name,
        model_version=method.model_version,
        notes=method.notes,
        result=ResultPayload(
            result_state=DataState(result.result_state),
            accuracy=result.accuracy,
            latency_p50_ms=result.latency_p50_ms,
            cost_per_1k=result.cost_per_1k,
            deterministic=result.deterministic,
            auditable=result.auditable,
            metric_definition_version=result.metric_definition_version,
            raw_artifact_uri=result.raw_artifact_uri,
            measured_at=result.measured_at.isoformat() if result.measured_at else None,
            cost_state=DataState(result.cost_state),
            run_id=result.run_id,
            sample_count=result.sample_count,
        ),
    )


def default_requirements(problem: ProblemModel) -> RequirementsPayload:
    """The problem's default operating requirements.

    Falls back to the first stored profile if the conventional ``default`` name
    is absent, so a problem is never left without a starting point.
    """
    profiles = problem.requirement_profiles
    if not profiles:
        raise ValueError(f"Problem {problem.slug!r} has no requirement profile")
    chosen = next((p for p in profiles if p.name == DEFAULT_PROFILE_NAME), profiles[0])
    return RequirementsPayload(
        min_accuracy=chosen.min_accuracy,
        max_latency_ms=chosen.max_latency_ms,
        auditability_required=chosen.auditability_required,
        monthly_volume=chosen.monthly_volume,
    )


def _to_detail(problem: ProblemModel) -> ProblemDetail:
    dataset = problem.dataset_versions[0]
    # Methods are ordered by complexity so the API mirrors how the decision
    # rule reads them.
    methods = sorted(problem.methods, key=lambda m: (m.complexity_rank, m.stable_key))
    return ProblemDetail(
        **_to_summary(problem).model_dump(),
        rationale=problem.rationale,
        dataset=DatasetPayload(
            name=dataset.name,
            version=dataset.version,
            sample_count_label=dataset.sample_count_label,
            sha256=dataset.sha256,
            license=dataset.license,
            source_url=dataset.source_url,
            provenance_notes=dataset.provenance_notes,
        ),
        default_requirements=default_requirements(problem),
        methods=tuple(_to_method_payload(method) for method in methods),
    )


def list_problems(repository: ProblemRepository) -> tuple[ProblemSummary, ...]:
    return tuple(_to_summary(problem) for problem in repository.list_problems())


def get_problem_model(repository: ProblemRepository, slug: str) -> ProblemModel:
    problem = repository.get_by_slug(slug)
    if problem is None:
        raise ProblemNotFoundError(
            f"No benchmark problem exists with slug {slug!r}.",
            {"slug": slug},
        )
    return problem


def get_problem_detail(repository: ProblemRepository, slug: str) -> ProblemDetail:
    return _to_detail(get_problem_model(repository, slug))
