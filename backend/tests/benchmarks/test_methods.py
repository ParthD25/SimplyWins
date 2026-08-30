"""Method behaviour, independent of any particular score."""

from __future__ import annotations

import pytest

from app.benchmarks.base import Example, MethodConfig
from app.benchmarks.methods.support_ticket_routing.keyword_rules import (
    KeywordRulesMethod,
)
from app.benchmarks.methods.support_ticket_routing.tfidf_logreg import (
    TfidfLogisticRegressionMethod,
)
from app.benchmarks.runner import load_dataset

LABELS = ("account", "billing", "other", "shipping", "technical")


def example(text: str) -> Example:
    return Example(example_id="x", text=text, label="other")


class TestKeywordRules:
    def test_needs_no_training(self) -> None:
        method = KeywordRulesMethod()
        method.setup(MethodConfig(seed=1))

        assert method.predict([example("please refund my invoice")]) == ["billing"]

    def test_routes_obvious_tickets(self) -> None:
        method = KeywordRulesMethod()
        method.setup(MethodConfig(seed=1))
        cases = {
            "I want a refund for the charge on my card": "billing",
            "the app crashes with a 500 error": "technical",
            "I cannot log in, my password fails": "account",
            "my parcel has not arrived, tracking is stuck": "shipping",
        }

        for text, expected in cases.items():
            assert method.predict([example(text)]) == [expected], text

    def test_falls_back_to_other_when_nothing_matches(self) -> None:
        method = KeywordRulesMethod()
        method.setup(MethodConfig(seed=1))

        assert method.predict([example("hello there")]) == ["other"]

    def test_is_deterministic(self) -> None:
        method = KeywordRulesMethod()
        method.setup(MethodConfig(seed=1))
        text = example("my invoice is wrong and the app crashed")

        assert method.predict([text]) == method.predict([text])

    def test_decisions_are_explainable(self) -> None:
        """Auditability is a claim the method makes; this is what backs it."""
        method = KeywordRulesMethod()

        hits = method.explain("refund the invoice charge")

        assert hits["billing"] >= 3
        assert sum(hits.values()) == hits["billing"]

    def test_declares_itself_auditable_and_deterministic(self) -> None:
        metadata = KeywordRulesMethod().metadata()

        assert metadata.deterministic is True
        assert metadata.auditable is True
        assert metadata.complexity_rank == 1
        assert metadata.provider is None


class TestTfidfLogisticRegression:
    def test_refuses_to_predict_before_setup(self) -> None:
        with pytest.raises(RuntimeError, match="setup"):
            TfidfLogisticRegressionMethod().predict([example("anything")])

    def test_requires_training_examples(self) -> None:
        with pytest.raises(ValueError, match="requires training examples"):
            TfidfLogisticRegressionMethod().setup(MethodConfig(seed=1))

    def test_predicts_only_known_labels(self) -> None:
        train, test, _ = load_dataset("support-ticket-routing")
        method = TfidfLogisticRegressionMethod()
        method.setup(MethodConfig(seed=7, training_examples=tuple(train), labels=LABELS))

        predictions = method.predict(test[:200])

        assert set(predictions) <= set(LABELS)

    def test_is_reproducible_across_fits(self) -> None:
        """Two fits on the same data and seed must agree, or the published
        accuracy is not reproducible."""
        train, test, _ = load_dataset("support-ticket-routing")
        sample = test[:150]

        first = TfidfLogisticRegressionMethod()
        first.setup(MethodConfig(seed=7, training_examples=tuple(train), labels=LABELS))
        second = TfidfLogisticRegressionMethod()
        second.setup(MethodConfig(seed=7, training_examples=tuple(train), labels=LABELS))

        assert list(first.predict(sample)) == list(second.predict(sample))

    def test_declares_higher_complexity_than_rules(self) -> None:
        metadata = TfidfLogisticRegressionMethod().metadata()

        assert metadata.complexity_rank > KeywordRulesMethod().metadata().complexity_rank
        assert metadata.method_class == "traditional-ml"


class TestCostModel:
    def test_cost_scales_with_latency(self) -> None:
        model = KeywordRulesMethod().metadata().cost_model

        assert model.cost_per_1k(20.0) == pytest.approx(2 * model.cost_per_1k(10.0))

    def test_cost_model_carries_its_source_and_date(self) -> None:
        """A cost figure without a dated source is not defensible."""
        model = KeywordRulesMethod().metadata().cost_model

        assert model.source
        assert model.as_of
        assert model.rate_usd > 0
