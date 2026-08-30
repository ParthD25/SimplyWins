"""Hosted-LLM classification, covering both the small-model and frontier tiers.

Two of the product's four complexity tiers are hosted models rather than code
that runs here. Both are served through the same class, differing only in which
model answers: a small, cheap model and a frontier one. That keeps the
comparison clean — identical prompt, identical parsing, identical timing — so a
difference between the tiers is a difference in the model and not in the
harness around it.

Three decisions worth stating, because each trades something away:

*Cost is measured, not projected.* Every response reports the tokens it used,
so cost here is arithmetic on observed usage at a published rate — the only
method in the project whose cost is MEASURED rather than ESTIMATED.

*No server-side refusal fallback.* Anthropic can route a refused request to a
different model automatically. That is the right default for an application and
the wrong one for a benchmark, because a silent model swap would put another
model's answers in this model's column. Refusals are counted and reported
instead.

*A sample, not the full split.* Running every test item through a frontier
model costs real money and the rules and ML arms are free, so the LLM tiers run
on a stratified sample. ``sample_count`` on the run record always states how
many items a number came from, and it is not the same for every method.
"""

from __future__ import annotations

import os
import random
from collections.abc import Sequence
from dataclasses import dataclass

from app.benchmarks.base import CostModel, Example, MethodConfig, MethodMetadata

IMPLEMENTATION_VERSION = "1.0.0"
PROMPT_VERSION = "1.0.0"

API_KEY_ENV = "ANTHROPIC_API_KEY"


@dataclass(frozen=True, slots=True)
class ModelTier:
    """A model plus the facts needed to price and describe it."""

    method_id: str
    model: str
    name: str
    short_name: str
    method_class: str
    complexity_rank: int
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    # Effort is only accepted by the frontier tier; the small model rejects it.
    supports_effort: bool


SMALL_MODEL = ModelTier(
    method_id="small-model",
    model="claude-haiku-4-5",
    name="Small Hosted Model (Claude Haiku 4.5)",
    short_name="Small model",
    method_class="small-model",
    complexity_rank=3,
    input_usd_per_mtok=1.00,
    output_usd_per_mtok=5.00,
    supports_effort=False,
)

FRONTIER_MODEL = ModelTier(
    method_id="frontier-llm",
    model="claude-opus-5",
    name="Frontier LLM (Claude Opus 5)",
    short_name="Frontier LLM",
    method_class="frontier-llm",
    complexity_rank=4,
    input_usd_per_mtok=5.00,
    output_usd_per_mtok=25.00,
    supports_effort=True,
)

TIERS = {tier.method_id: tier for tier in (SMALL_MODEL, FRONTIER_MODEL)}


def api_key_present() -> bool:
    return bool(os.environ.get(API_KEY_ENV))


class LlmClassifierMethod:
    """Classifies one document per request against a fixed label set."""

    def __init__(self, tier: ModelTier, task_description: str = "") -> None:
        self._tier = tier
        self._task = task_description
        self._labels: tuple[str, ...] = ()
        self._client: object | None = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.refusals = 0
        self.unparseable = 0

    def setup(self, config: MethodConfig) -> None:
        if not config.labels:
            raise ValueError("The LLM classifier needs the label set to constrain output")
        self._labels = config.labels

        if not api_key_present():
            raise RuntimeError(
                f"{API_KEY_ENV} is not set. The hosted-model tiers cannot run without "
                "it; their results stay unmeasured rather than being estimated."
            )

        import anthropic

        self._client = anthropic.Anthropic()

    @property
    def _system_prompt(self) -> str:
        labels = ", ".join(self._labels)
        return (
            f"{self._task}\n\n"
            f"Choose exactly one label from this list: {labels}.\n"
            "Answer only with the label. Do not explain."
        )

    def _request_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "model": self._tier.model,
            # Classification: the answer is one short label, so a large budget
            # would only buy the chance to run long.
            "max_tokens": 256,
            "system": self._system_prompt,
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {"label": {"type": "string", "enum": list(self._labels)}},
                        "required": ["label"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        if self._tier.supports_effort:
            # Thinking stays on (its default on this model) and effort comes
            # down instead: disabling thinking on Opus 5 can leak reasoning into
            # the visible answer, which is exactly what breaks label parsing.
            kwargs["output_config"] = {**kwargs["output_config"], "effort": "low"}  # type: ignore[dict-item]
        return kwargs

    def _classify(self, text: str) -> str:
        import json

        assert self._client is not None
        response = self._client.messages.create(  # type: ignore[attr-defined]
            **self._request_kwargs(),
            messages=[{"role": "user", "content": text}],
        )

        if getattr(response, "stop_reason", None) == "refusal":
            self.refusals += 1
            return ""

        usage = getattr(response, "usage", None)
        if usage is not None:
            self.input_tokens += getattr(usage, "input_tokens", 0) or 0
            self.output_tokens += getattr(usage, "output_tokens", 0) or 0

        block = next((b for b in response.content if b.type == "text"), None)
        if block is None:
            self.unparseable += 1
            return ""
        try:
            label = json.loads(block.text)["label"]
        except (ValueError, KeyError, TypeError):
            self.unparseable += 1
            return ""
        return label if label in self._labels else ""

    def predict(self, examples: Sequence[Example]) -> Sequence[str]:
        return [self._classify(example.text) for example in examples]

    def measured_cost_per_1k(self, items: int) -> float:
        """Cost for 1,000 items from the tokens this run actually used."""
        if items <= 0:
            return 0.0
        spend = (
            self.input_tokens / 1_000_000 * self._tier.input_usd_per_mtok
            + self.output_tokens / 1_000_000 * self._tier.output_usd_per_mtok
        )
        return spend / items * 1_000

    def metadata(self) -> MethodMetadata:
        return MethodMetadata(
            method_id=self._tier.method_id,
            name=self._tier.name,
            short_name=self._tier.short_name,
            method_class=self._tier.method_class,
            complexity_rank=self._tier.complexity_rank,
            implementation_version=IMPLEMENTATION_VERSION,
            # A hosted model is not guaranteed to return the same answer twice,
            # and its weights can change under a stable name.
            deterministic=False,
            auditable=False,
            cost_model=CostModel(
                basis="Observed input and output tokens at published list prices",
                rate_usd=self._tier.input_usd_per_mtok,
                rate_unit=(
                    f"USD per 1M input tokens (output {self._tier.output_usd_per_mtok:.2f})"
                ),
                source="Anthropic published pricing",
                as_of="2026-08",
            ),
            provider="anthropic",
            model_name=self._tier.model,
            prompt_version=PROMPT_VERSION,
            notes="Run on a stratified sample; see sample_count.",
        )


def stratified_sample(examples: Sequence[Example], *, size: int, seed: int) -> list[Example]:
    """An equal number per label, so a sampled score is not a sampling artefact."""
    from collections import defaultdict

    by_label: dict[str, list[Example]] = defaultdict(list)
    for example in examples:
        by_label[example.label].append(example)

    per_label = max(1, size // len(by_label))
    rng = random.Random(seed)
    picked: list[Example] = []
    for label in sorted(by_label):
        bucket = sorted(by_label[label], key=lambda e: e.example_id)
        rng.shuffle(bucket)
        picked.extend(bucket[:per_label])
    rng.shuffle(picked)
    return picked
