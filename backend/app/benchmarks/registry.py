"""Maps a problem slug to its dataset and the methods competing on it.

Every problem here is backed by a real, publicly published corpus. Problems
whose data would have to be written in this repository are not registered:
an earlier version of this benchmark carried six problems of which five had no
measurements at all and one was measured against text its own author had
written. Three real problems say more than six illustrative ones.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.benchmarks.base import BenchmarkMethod
from app.benchmarks.methods import vocabularies as vocab
from app.benchmarks.methods.keyword_rules import KeywordRulesMethod
from app.benchmarks.methods.llm_classifier import (
    FRONTIER_MODEL,
    SMALL_MODEL,
    LlmClassifierMethod,
)
from app.benchmarks.methods.tfidf_logreg import TfidfLogisticRegressionMethod


@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    slug: str
    dataset_module: str
    definition_version: str
    methods: dict[str, Callable[[], BenchmarkMethod]]
    # The analyser each problem selected on a validation split carved from its
    # training data only. Recorded here rather than hard-coded in the method so
    # the choice is visible next to the problem it was made for.
    ml_analyzer: str = "word"
    task_description: str = ""
    llm_sample_size: int = 210
    labels: tuple[str, ...] = field(default_factory=tuple)


def _definition(
    *,
    slug: str,
    dataset_module: str,
    vocabulary: dict[str, tuple[str, ...]],
    priority: tuple[str, ...],
    fallback: str,
    analyzer: str,
    task: str,
    labels: tuple[str, ...],
    llm_sample_size: int = 210,
) -> BenchmarkDefinition:
    return BenchmarkDefinition(
        slug=slug,
        dataset_module=dataset_module,
        definition_version="2.0.0",
        ml_analyzer=analyzer,
        task_description=task,
        labels=labels,
        llm_sample_size=llm_sample_size,
        methods={
            "rules": lambda: KeywordRulesMethod(
                vocabulary, priority=priority, fallback_label=fallback
            ),
            "ml": lambda: TfidfLogisticRegressionMethod(analyzer),
            "small-model": lambda: LlmClassifierMethod(SMALL_MODEL, task),
            "frontier-llm": lambda: LlmClassifierMethod(FRONTIER_MODEL, task),
        },
    )


BENCHMARKS: dict[str, BenchmarkDefinition] = {
    "support-request-routing": _definition(
        slug="support-request-routing",
        dataset_module="app.benchmarks.datasets.cfpb_complaints.build",
        vocabulary=vocab.CFPB_VOCABULARY,
        priority=vocab.CFPB_PRIORITY,
        fallback="bank-account",
        analyzer="word",
        task=("You are routing a consumer finance complaint to the team that handles it."),
        labels=(
            "bank-account",
            "cards",
            "credit-reporting",
            "debt-collection",
            "loans",
            "money-transfer",
            "mortgage",
        ),
    ),
    "spam-detection": _definition(
        slug="spam-detection",
        dataset_module="app.benchmarks.datasets.sms_spam.build",
        vocabulary=vocab.SPAM_VOCABULARY,
        priority=vocab.SPAM_PRIORITY,
        fallback="ham",
        analyzer="char_wb",
        task="You are deciding whether an SMS message is unsolicited spam.",
        labels=("ham", "spam"),
        llm_sample_size=200,
    ),
    "sentiment-classification": _definition(
        slug="sentiment-classification",
        dataset_module="app.benchmarks.datasets.sst2_sentiment.build",
        vocabulary=vocab.SENTIMENT_VOCABULARY,
        priority=vocab.SENTIMENT_PRIORITY,
        fallback="positive",
        analyzer="char_wb",
        task="You are judging the sentiment a film review sentence expresses.",
        labels=("negative", "positive"),
        llm_sample_size=200,
    ),
}


def get_benchmark(slug: str) -> BenchmarkDefinition:
    if slug not in BENCHMARKS:
        known = ", ".join(sorted(BENCHMARKS))
        raise KeyError(f"No benchmark registered for slug {slug!r}. Known: {known}")
    return BENCHMARKS[slug]
