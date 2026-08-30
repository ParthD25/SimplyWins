"""Core types for the benchmark runner.

A benchmark compares implementation classes on one task, one dataset version,
and one metric definition. Everything a method needs to declare about itself
lives in ``MethodMetadata`` so a run record can satisfy section 4 of
PROJECT_STANDARD.md without the runner knowing anything method-specific.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Cost figures across the project are quoted per 1,000 units of work.
COST_BATCH_SIZE = 1_000


@dataclass(frozen=True, slots=True)
class Example:
    """One labelled item. ``label`` is the ground truth the metric compares to."""

    example_id: str
    text: str
    label: str


@dataclass(frozen=True, slots=True)
class MethodConfig:
    """Everything a method may use to prepare itself.

    ``training_examples`` is empty for methods that do not train. A method that
    ignores it (deterministic rules) is as valid as one that fits on it.
    """

    seed: int
    training_examples: tuple[Example, ...] = ()
    labels: tuple[str, ...] = ()
    options: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CostModel:
    """How a method's cost per 1,000 items is derived.

    Cost is never measured directly — it is computed from measured latency plus
    a documented rate. That makes any cost figure ESTIMATED under section 5 of
    the standard even when the latency behind it is MEASURED, so the assumption
    and its source travel with the number.
    """

    basis: str
    rate_usd: float
    rate_unit: str
    source: str
    as_of: str

    def cost_per_1k(self, median_latency_ms: float) -> float:
        """Project cost for 1,000 sequential items at the measured latency."""
        compute_hours = (median_latency_ms / 1000.0) * COST_BATCH_SIZE / 3600.0
        return compute_hours * self.rate_usd


@dataclass(frozen=True, slots=True)
class MethodMetadata:
    """Provenance a method declares about itself."""

    method_id: str
    name: str
    short_name: str
    method_class: str
    complexity_rank: int
    implementation_version: str
    deterministic: bool
    auditable: bool
    cost_model: CostModel
    provider: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    notes: str = ""


@runtime_checkable
class BenchmarkMethod(Protocol):
    """The contract every competing implementation satisfies.

    ``predict`` takes a sequence so a method may batch internally, but the
    runner calls it one example at a time when timing, because single-item
    latency is what a request-response deployment actually experiences.
    """

    def setup(self, config: MethodConfig) -> None: ...

    def predict(self, examples: Sequence[Example]) -> Sequence[str]: ...

    def metadata(self) -> MethodMetadata: ...
