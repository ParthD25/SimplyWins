"""The checks that say whether a benchmark result means anything.

The last test here is the important one: it reconstructs the failure this
module exists because of — a corpus and a rule vocabulary written by the same
author — and asserts the audit reports it.
"""

from __future__ import annotations

from app.benchmarks import leakage
from app.benchmarks.base import Example, MethodConfig
from app.benchmarks.methods.keyword_rules import KeywordRulesMethod


def _ex(rows: list[tuple[str, str]]) -> list[Example]:
    return [Example(str(i), text, label) for i, (text, label) in enumerate(rows)]


def test_majority_baseline_is_the_score_for_guessing_the_common_label() -> None:
    train = _ex([("a", "yes")] * 8 + [("b", "no")] * 2)
    test = _ex([("c", "yes")] * 7 + [("d", "no")] * 3)
    label, accuracy = leakage.majority_baseline(train, test)
    assert label == "yes"
    assert accuracy == 70.0


def test_contamination_counts_test_text_that_also_appears_in_training() -> None:
    train = _ex([("shared text", "a"), ("train only", "a")])
    test = _ex([("SHARED TEXT", "a"), ("test only", "a")])
    hits, rate = leakage.contamination(train, test)
    assert hits == 1
    assert rate == 50.0


def test_clean_splits_report_no_contamination() -> None:
    assert leakage.contamination(_ex([("x", "a")]), _ex([("y", "a")])) == (0, 0.0)


def test_a_single_word_term_must_match_a_whole_token() -> None:
    """Otherwise 'card' is credited to 'cardiac' and attestation is overstated."""
    train = _ex([("the cardiac ward", "a")])
    assert leakage.attested_terms(["card"], train) == set()
    assert leakage.attested_terms(["cardiac"], train) == {"cardiac"}


def test_a_multi_word_term_matches_as_a_phrase() -> None:
    train = _ex([("please issue a credit card refund", "a")])
    assert leakage.attested_terms(["credit card"], train) == {"credit card"}


def test_audit_reports_chance_from_the_label_count() -> None:
    audit = leakage.audit(_ex([("a", "x")]), _ex([("b", "x")]), label_count=4)
    assert audit.chance_accuracy == 25.0


def test_audit_serialises_for_the_run_record() -> None:
    audit = leakage.audit(_ex([("a", "x")]), _ex([("b", "x")]), label_count=2)
    payload = audit.as_dict()
    assert payload["chance_accuracy"] == 50.0
    assert payload["term_provenance"] is None


class TestItCatchesTheOriginalBug:
    """A vocabulary fitted to its own corpus must be visible as one.

    This reproduces, in miniature, the situation that made the earlier synthetic
    benchmark meaningless: the terms that carry the score are exactly the terms
    that appear in the data, and terms the corpus never uses carry nothing.
    """

    TRAIN = _ex(
        [("invoice refund billing", "billing")] * 10 + [("crash error broken", "technical")] * 10
    )
    TEST = _ex([("invoice refund", "billing")] * 5 + [("crash error", "technical")] * 5)

    def _method(self) -> KeywordRulesMethod:
        vocab = {
            # Attested: lifted straight from the corpus.
            "billing": ("invoice", "refund", "remittance"),
            "technical": ("crash", "error", "kernel panic"),
        }
        method = KeywordRulesMethod(
            vocab, priority=("billing", "technical"), fallback_label="billing"
        )
        method.setup(MethodConfig(seed=0))
        return method

    def _accuracy(self, method: KeywordRulesMethod) -> float:
        predicted = method.predict(self.TEST)
        return sum(p == e.label for p, e in zip(predicted, self.TEST, strict=True)) / len(self.TEST)

    def test_the_attested_half_carries_the_whole_score(self) -> None:
        method = self._method()
        attested = leakage.attested_terms(method.terms, self.TRAIN)
        assert self._accuracy(method.with_terms(attested)) == self._accuracy(method)

    def test_the_unattested_half_carries_nothing(self) -> None:
        method = self._method()
        attested = leakage.attested_terms(method.terms, self.TRAIN)
        unattested = set(method.terms) - attested
        assert unattested, "the fixture needs terms the corpus never uses"
        # With no attested term left, every document falls through to the
        # fallback label, which is chance on a balanced set.
        assert self._accuracy(method.with_terms(unattested)) <= 0.5

    def test_provenance_records_the_split(self) -> None:
        method = self._method()
        attested = leakage.attested_terms(method.terms, self.TRAIN)
        provenance = leakage.TermProvenance(
            total_terms=len(method.terms),
            attested_terms=len(attested),
            unattested_terms=len(method.terms) - len(attested),
            accuracy_all_terms=100.0,
            accuracy_attested_only=100.0,
            accuracy_unattested_only=50.0,
        )
        audit = leakage.audit(self.TRAIN, self.TEST, label_count=2, term_provenance=provenance)
        payload = audit.as_dict()
        assert payload["term_provenance"]["attested_fraction"] == round(
            len(attested) / len(method.terms), 4
        )
