"""Method behaviour, including the guards that keep the baselines honest."""

from __future__ import annotations

import pytest

from app.benchmarks.base import Example, MethodConfig
from app.benchmarks.methods.keyword_rules import KeywordRulesMethod
from app.benchmarks.methods.llm_classifier import (
    FRONTIER_MODEL,
    SMALL_MODEL,
    LlmClassifierMethod,
    stratified_sample,
)
from app.benchmarks.methods.tfidf_logreg import ANALYZERS, TfidfLogisticRegressionMethod

VOCAB = {"billing": ("invoice", "refund"), "other": ()}
PRIORITY = ("billing", "other")


def _rules() -> KeywordRulesMethod:
    method = KeywordRulesMethod(VOCAB, priority=PRIORITY, fallback_label="other")
    method.setup(MethodConfig(seed=0))
    return method


def test_rules_pick_the_label_with_the_most_matches() -> None:
    assert _rules().predict([Example("1", "my invoice needs a refund", "billing")]) == ["billing"]


def test_rules_fall_back_when_nothing_matches() -> None:
    assert _rules().predict([Example("1", "hello there", "other")]) == ["other"]


def test_rules_are_deterministic() -> None:
    example = [Example("1", "invoice", "billing")]
    assert _rules().predict(example) == _rules().predict(example)


def test_rules_expose_their_vocabulary_for_auditing() -> None:
    """The audit cannot grade a vocabulary it cannot see."""
    assert set(_rules().terms) == {"invoice", "refund"}


def test_restricting_terms_produces_an_independent_method() -> None:
    """The ablation must not mutate the method it is measuring."""
    method = _rules()
    restricted = method.with_terms({"invoice"})
    assert set(restricted.terms) == {"invoice"}
    assert set(method.terms) == {"invoice", "refund"}


def test_restricting_to_nothing_predicts_only_the_fallback() -> None:
    method = _rules().with_terms(set())
    method.setup(MethodConfig(seed=0))
    assert method.predict([Example("1", "invoice refund", "billing")]) == ["other"]


def test_ml_requires_training_examples() -> None:
    with pytest.raises(ValueError, match="requires training examples"):
        TfidfLogisticRegressionMethod("word").setup(MethodConfig(seed=0))


def test_ml_rejects_an_unknown_analyzer() -> None:
    with pytest.raises(ValueError, match="Unknown analyzer"):
        TfidfLogisticRegressionMethod("bag-of-vibes")


@pytest.mark.parametrize("analyzer", sorted(ANALYZERS))
def test_ml_learns_a_separable_task(analyzer: str) -> None:
    train = tuple(
        Example(str(i), text, label)
        for i, (text, label) in enumerate(
            [("refund my invoice", "billing")] * 8 + [("the app crashed", "technical")] * 8
        )
    )
    method = TfidfLogisticRegressionMethod(analyzer)
    method.setup(MethodConfig(seed=0, training_examples=train))
    assert method.predict([Example("x", "invoice refund please", "billing")]) == ["billing"]


class TestLlmTiers:
    """The hosted tiers must refuse to invent numbers, and must stay distinct."""

    def test_setup_fails_loudly_without_a_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        method = LlmClassifierMethod(FRONTIER_MODEL, "task")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            method.setup(MethodConfig(seed=0, labels=("a", "b")))

    def test_setup_requires_the_label_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        with pytest.raises(ValueError, match="label set"):
            LlmClassifierMethod(SMALL_MODEL, "task").setup(MethodConfig(seed=0))

    def test_the_two_tiers_differ_in_model_and_rank(self) -> None:
        small = LlmClassifierMethod(SMALL_MODEL, "t").metadata()
        frontier = LlmClassifierMethod(FRONTIER_MODEL, "t").metadata()
        assert small.model_name != frontier.model_name
        assert small.complexity_rank < frontier.complexity_rank

    def test_hosted_tiers_are_neither_deterministic_nor_auditable(self) -> None:
        meta = LlmClassifierMethod(FRONTIER_MODEL, "t").metadata()
        assert meta.deterministic is False
        assert meta.auditable is False

    def test_cost_comes_from_observed_tokens(self) -> None:
        method = LlmClassifierMethod(FRONTIER_MODEL, "t")
        method.input_tokens = 1_000_000
        method.output_tokens = 1_000_000
        # $5 in + $25 out over 100 items, projected to 1,000.
        assert method.measured_cost_per_1k(100) == pytest.approx(300.0)

    def test_cost_is_zero_before_anything_ran(self) -> None:
        assert LlmClassifierMethod(SMALL_MODEL, "t").measured_cost_per_1k(0) == 0.0


def test_stratified_sample_is_balanced_and_reproducible() -> None:
    pool = [Example(f"{label}-{i}", "text", label) for label in "ab" for i in range(50)]
    first = stratified_sample(pool, size=20, seed=1)
    assert [e.example_id for e in first] == [
        e.example_id for e in stratified_sample(pool, size=20, seed=1)
    ]
    labels = {e.label for e in first}
    assert labels == {"a", "b"}
    assert sum(e.label == "a" for e in first) == sum(e.label == "b" for e in first)
