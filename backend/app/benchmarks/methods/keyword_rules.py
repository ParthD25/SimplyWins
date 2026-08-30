"""Keyword scoring — the deterministic baseline, shared by every problem.

A vocabulary per label, scored by how many of its terms a document contains,
with a fixed priority order breaking ties. Every decision is inspectable, which
is what makes the method auditable, and the same input always yields the same
output.

On the honesty of the vocabularies: they are hand-written from ordinary domain
language, and they were checked against the *training* split only. That is a
weaker claim than an earlier version of this file made — it asserted the
vocabulary had been chosen without consulting the data at all, which was not
true and was measurably not true. Rather than repeat an unverifiable claim,
every run now reports what fraction of a vocabulary actually occurs in the
training corpus and scores the attested and unattested halves separately
(``app.benchmarks.leakage``). The reader can judge the baseline from that
instead of taking the author's word.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.benchmarks.base import CostModel, Example, MethodConfig, MethodMetadata

IMPLEMENTATION_VERSION = "3.0.0"

# Rules run on the same general-purpose CPU as the rest of the stack; cost is
# projected from measured latency at a published on-demand rate.
CPU_COST_MODEL = CostModel(
    basis="vCPU-seconds at an on-demand cloud rate",
    rate_usd=0.04,
    rate_unit="USD per vCPU-hour",
    source="Typical on-demand general-purpose vCPU pricing",
    as_of="2026-08",
)


class KeywordRulesMethod:
    """Scores each label's vocabulary against the document and takes the best.

    ``priority`` breaks ties in a fixed, declared order rather than by dict
    iteration, so the result does not depend on how the table was built.
    """

    def __init__(
        self,
        vocabulary: dict[str, tuple[str, ...]],
        *,
        priority: tuple[str, ...],
        fallback_label: str,
        notes: str = "",
    ) -> None:
        self._vocabulary = vocabulary
        self._priority = priority
        self._fallback = fallback_label
        self._notes = notes

    # Exposed so the leakage audit can split it against the training corpus.
    @property
    def terms(self) -> tuple[str, ...]:
        return tuple(term for label in self._priority for term in self._vocabulary[label])

    def with_terms(self, allowed: set[str]) -> KeywordRulesMethod:
        """A copy restricted to ``allowed``, used by the term-provenance ablation."""
        return KeywordRulesMethod(
            {
                label: tuple(t for t in terms if t in allowed)
                for label, terms in self._vocabulary.items()
            },
            priority=self._priority,
            fallback_label=self._fallback,
            notes=self._notes,
        )

    def setup(self, config: MethodConfig) -> None:
        """Nothing to fit. Declared explicitly so the no-op is deliberate."""
        return

    def _classify(self, text: str) -> str:
        lowered = text.lower()
        best_label = self._fallback
        best_score = 0
        for label in self._priority:
            score = sum(1 for term in self._vocabulary[label] if term in lowered)
            if score > best_score:
                best_label, best_score = label, score
        return best_label

    def predict(self, examples: Sequence[Example]) -> Sequence[str]:
        return [self._classify(example.text) for example in examples]

    def metadata(self) -> MethodMetadata:
        return MethodMetadata(
            method_id="rules",
            name="Keyword Rules",
            short_name="Rules",
            method_class="rules",
            complexity_rank=1,
            implementation_version=IMPLEMENTATION_VERSION,
            deterministic=True,
            auditable=True,
            cost_model=CPU_COST_MODEL,
            notes=self._notes,
        )
