"""Persistence models for benchmark problems, methods, and results.

These follow docs/DATA_MODEL.md. The tables covering benchmark *execution*
(BenchmarkRun) are defined here so run provenance has a home, but nothing
writes to them in this phase — the runner is Phase 3.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    """Section 4 of the standard requires run timestamps in UTC."""
    return datetime.now(UTC)


class Problem(Base):
    __tablename__ = "problem"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    decision_question: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    benchmark_definition_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    dataset_versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", lazy="selectin"
    )
    methods: Mapped[list[Method]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", lazy="selectin"
    )
    requirement_profiles: Mapped[list[RequirementProfile]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", lazy="selectin"
    )


class DatasetVersion(Base):
    __tablename__ = "dataset_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problem.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(32))
    sample_count_label: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provenance_notes: Mapped[str] = mapped_column(Text)

    problem: Mapped[Problem] = relationship(back_populates="dataset_versions")


class Method(Base):
    __tablename__ = "method"
    __table_args__ = (UniqueConstraint("problem_id", "stable_key", name="uq_method_problem_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problem.id", ondelete="CASCADE"))
    stable_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(80))
    method_class: Mapped[str] = mapped_column(String(40))
    complexity_rank: Mapped[int] = mapped_column(Integer)
    implementation_version: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str] = mapped_column(Text)

    problem: Mapped[Problem] = relationship(back_populates="methods")
    result: Mapped[Result | None] = relationship(
        back_populates="method", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class Result(Base):
    """The publishable figure for a method.

    ``result_state`` is what keeps demo numbers from being mistaken for
    evidence; it is required, never defaulted.
    """

    __tablename__ = "result"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    method_id: Mapped[str] = mapped_column(ForeignKey("method.id", ondelete="CASCADE"), unique=True)
    # Free-text run identifier from the published record. Not a foreign key:
    # the run may have been executed outside this database entirely.
    run_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result_state: Mapped[str] = mapped_column(String(16))
    accuracy: Mapped[float] = mapped_column(Float)
    task_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_p50_ms: Mapped[float] = mapped_column(Float)
    latency_p95_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_1k: Mapped[float] = mapped_column(Float)
    deterministic: Mapped[bool] = mapped_column(Boolean)
    auditable: Mapped[bool] = mapped_column(Boolean)
    # Null for a NOT_RUN method: nothing was measured, so no metric applied.
    metric_definition_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_artifact_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    measured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Cost is derived from measured latency plus an assumption, so it carries a
    # weaker state than the result it accompanies.
    cost_state: Mapped[str] = mapped_column(String(16), default="DEMO")
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The floors and contamination checks this figure must be read against,
    # stored as JSON. Serving a number without them invites the reader to
    # treat any accuracy as good news.
    leakage_audit_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    method: Mapped[Method] = relationship(back_populates="result")


class BenchmarkRun(Base):
    """Immutable record of one benchmark execution.

    Defined now so the provenance columns required by section 4 of the standard
    exist alongside the data model they describe. Populating it is Phase 3.
    """

    __tablename__ = "benchmark_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problem.id", ondelete="CASCADE"))
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_version.id", ondelete="RESTRICT")
    )
    method_id: Mapped[str] = mapped_column(ForeignKey("method.id", ondelete="CASCADE"))
    code_commit_sha: Mapped[str] = mapped_column(String(40))
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    environment_json: Mapped[str] = mapped_column(Text)
    sample_count: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RequirementProfile(Base):
    """A named set of operating requirements, e.g. the problem's defaults."""

    __tablename__ = "requirement_profile"
    __table_args__ = (UniqueConstraint("problem_id", "name", name="uq_profile_problem_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problem.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    min_accuracy: Mapped[float] = mapped_column(Float)
    max_latency_ms: Mapped[int] = mapped_column(Integer)
    auditability_required: Mapped[bool] = mapped_column(Boolean)
    monthly_volume: Mapped[int] = mapped_column(Integer)

    problem: Mapped[Problem] = relationship(back_populates="requirement_profiles")
