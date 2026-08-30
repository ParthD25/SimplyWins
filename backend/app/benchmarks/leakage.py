"""Checks that ask whether a benchmark result means anything.

An accuracy figure is only evidence if the experiment could have produced a low
one. This module exists because an earlier version of this benchmark could not:
the corpus was written in this repository and the deterministic baseline was
written by the same author, so the rules were scored on vocabulary they had
helped choose. The number looked like a measurement and was closer to a mirror.

Three things are checked on every run, and all three are recorded in the run
record whether they pass or fail:

* **A floor.** Always predicting the most common label costs nothing and is not
  intelligence. A method is only informative to the extent it beats that.
* **Contamination.** Text appearing in both splits lets a method that memorises
  score without generalising.
* **Term provenance** (rule-style methods only). Splits a method's vocabulary by
  whether each term actually occurs in the training data, then scores the two
  halves separately. A baseline whose terms are all attested in the data it was
  built from is a fitted model wearing the word "rules"; one whose unattested
  terms carry real signal is doing domain work.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from app.benchmarks.base import Example

_WORD = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True, slots=True)
class TermProvenance:
    """How a rule vocabulary divides against the training corpus."""

    total_terms: int
    attested_terms: int
    unattested_terms: int
    accuracy_all_terms: float
    accuracy_attested_only: float
    accuracy_unattested_only: float

    @property
    def attested_fraction(self) -> float:
        return self.attested_terms / self.total_terms if self.total_terms else 0.0

    @property
    def unattested_lift_over_floor(self) -> float:
        """How far the unattested half beats chance. Near zero means the
        vocabulary is entirely fitted to the corpus."""
        return self.accuracy_unattested_only


@dataclass(frozen=True, slots=True)
class LeakageAudit:
    majority_label: str
    majority_baseline_accuracy: float
    chance_accuracy: float
    train_size: int
    test_size: int
    contaminated_examples: int
    contamination_rate: float
    term_provenance: TermProvenance | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["notes"] = list(self.notes)
        if self.term_provenance is not None:
            payload["term_provenance"] = {
                **asdict(self.term_provenance),
                "attested_fraction": round(self.term_provenance.attested_fraction, 4),
            }
        return payload


def majority_baseline(train: Sequence[Example], test: Sequence[Example]) -> tuple[str, float]:
    """The score for always guessing the most common training label."""
    if not train or not test:
        return "", 0.0
    label, _ = Counter(e.label for e in train).most_common(1)[0]
    correct = sum(1 for e in test if e.label == label)
    return label, correct / len(test) * 100.0


def contamination(train: Sequence[Example], test: Sequence[Example]) -> tuple[int, float]:
    """Test items whose text also appears in training, compared case-insensitively."""
    if not test:
        return 0, 0.0
    seen = {e.text.strip().lower() for e in train}
    hits = sum(1 for e in test if e.text.strip().lower() in seen)
    return hits, hits / len(test) * 100.0


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def attested_terms(terms: Sequence[str], train: Sequence[Example]) -> set[str]:
    """Terms that actually occur in the training corpus.

    A multi-word term counts as attested when it appears as a substring; a
    single word must match a whole token, so "card" is not credited to
    "cardiac".
    """
    corpus = " ".join(e.text.lower() for e in train)
    vocabulary = _tokens(corpus)
    found: set[str] = set()
    for term in terms:
        lowered = term.lower()
        if " " in lowered:
            if lowered in corpus:
                found.add(term)
        elif lowered in vocabulary:
            found.add(term)
    return found


def audit(
    train: Sequence[Example],
    test: Sequence[Example],
    *,
    label_count: int,
    term_provenance: TermProvenance | None = None,
    notes: Sequence[str] = (),
) -> LeakageAudit:
    label, baseline = majority_baseline(train, test)
    hits, rate = contamination(train, test)
    return LeakageAudit(
        majority_label=label,
        majority_baseline_accuracy=round(baseline, 4),
        chance_accuracy=round(100.0 / label_count, 4) if label_count else 0.0,
        train_size=len(train),
        test_size=len(test),
        contaminated_examples=hits,
        contamination_rate=round(rate, 4),
        term_provenance=term_provenance,
        notes=tuple(notes),
    )
