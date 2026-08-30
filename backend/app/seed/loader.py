"""Load versioned seed definitions into the database.

The backend owns the problem definitions from this phase onward. The seed files
under ``app/seed/<version>/`` are the source of truth; ``frontend/assets/data.js``
keeps its copy only so the static prototype stays viewable offline.

Seeding is idempotent at the problem level: a slug that already exists is left
alone rather than overwritten, so restarting the app never silently mutates
stored definitions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.models.benchmark import DatasetVersion, Method, Problem, RequirementProfile, Result
from app.repositories.problem_repository import ProblemRepository
from app.schemas.common import ProblemStatus
from app.schemas.problem import DatasetPayload, MethodPayload, RequirementsPayload

logger = logging.getLogger(__name__)

SEED_ROOT = Path(__file__).parent
DEFAULT_PROFILE_NAME = "default"


class SeedProblem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str
    title: str
    category: str
    description: str
    decision_question: str
    rationale: str
    benchmark_definition_version: str
    status: ProblemStatus
    dataset: DatasetPayload
    default_requirements: RequirementsPayload
    methods: tuple[MethodPayload, ...]


class SeedFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seed_version: str
    data_state: str
    notice: str
    problems: tuple[SeedProblem, ...]


def seed_path(version: str) -> Path:
    return SEED_ROOT / version / "problems.json"


def load_seed_file(version: str) -> SeedFile:
    path = seed_path(version)
    if not path.is_file():
        raise FileNotFoundError(f"No seed definitions found at {path}")
    return SeedFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _to_orm(definition: SeedProblem) -> Problem:
    problem = Problem(
        slug=definition.slug,
        title=definition.title,
        category=definition.category,
        description=definition.description,
        decision_question=definition.decision_question,
        rationale=definition.rationale,
        benchmark_definition_version=definition.benchmark_definition_version,
        status=definition.status,
    )
    problem.dataset_versions.append(
        DatasetVersion(
            name=definition.dataset.name,
            version=definition.dataset.version,
            sample_count_label=definition.dataset.sample_count_label,
            sha256=definition.dataset.sha256,
            license=definition.dataset.license,
            source_url=definition.dataset.source_url,
            provenance_notes=definition.dataset.provenance_notes,
        )
    )
    problem.requirement_profiles.append(
        RequirementProfile(
            name=DEFAULT_PROFILE_NAME,
            min_accuracy=definition.default_requirements.min_accuracy,
            max_latency_ms=definition.default_requirements.max_latency_ms,
            auditability_required=definition.default_requirements.auditability_required,
            monthly_volume=definition.default_requirements.monthly_volume,
        )
    )
    for method in definition.methods:
        problem.methods.append(
            Method(
                stable_key=method.method_id,
                name=method.name,
                short_name=method.short_name,
                method_class=method.method_class.value,
                complexity_rank=method.complexity_rank,
                implementation_version=method.implementation_version,
                provider=method.provider,
                model_name=method.model_name,
                model_version=method.model_version,
                notes=method.notes,
                result=Result(
                    result_state=method.result.result_state.value,
                    accuracy=method.result.accuracy,
                    latency_p50_ms=method.result.latency_p50_ms,
                    cost_per_1k=method.result.cost_per_1k,
                    deterministic=method.result.deterministic,
                    auditable=method.result.auditable,
                    metric_definition_version=method.result.metric_definition_version,
                    raw_artifact_uri=method.result.raw_artifact_uri,
                    cost_state=method.result.cost_state.value,
                    sample_count=method.result.sample_count,
                    leakage_audit_json=(
                        method.result.leakage_audit.model_dump_json()
                        if method.result.leakage_audit is not None
                        else None
                    ),
                    run_id=method.result.run_id,
                    measured_at=(
                        datetime.fromisoformat(method.result.measured_at)
                        if method.result.measured_at
                        else None
                    ),
                ),
            )
        )
    return problem


def seed_problems(repository: ProblemRepository, version: str) -> int:
    """Insert any seed problem whose slug is not already stored.

    Returns the number of problems inserted.
    """
    seed = load_seed_file(version)
    inserted = 0
    for definition in seed.problems:
        if repository.get_by_slug(definition.slug) is not None:
            continue
        repository.add(_to_orm(definition))
        inserted += 1

    logger.info(
        "Seed applied",
        extra={
            "seed_version": seed.seed_version,
            "data_state": seed.data_state,
            "problems_in_file": len(seed.problems),
            "problems_inserted": inserted,
        },
    )
    return inserted
