"""Maps a problem slug to its dataset and the methods competing on it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.benchmarks.base import BenchmarkMethod
from app.benchmarks.methods.support_ticket_routing.keyword_rules import KeywordRulesMethod
from app.benchmarks.methods.support_ticket_routing.tfidf_logreg import (
    TfidfLogisticRegressionMethod,
)


@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    slug: str
    dataset_module: str
    definition_version: str
    methods: dict[str, Callable[[], BenchmarkMethod]]


BENCHMARKS: dict[str, BenchmarkDefinition] = {
    "support-ticket-routing": BenchmarkDefinition(
        slug="support-ticket-routing",
        dataset_module="app.benchmarks.datasets.support_ticket_routing.generate",
        definition_version="1.0.0",
        # Only methods that can actually be executed here are registered. The
        # small-model and frontier-LLM entries from the product spec are absent
        # because no model provider is connected — listing them with no
        # implementation would imply results that do not exist.
        methods={
            "ticket-rules": KeywordRulesMethod,
            "ticket-ml": TfidfLogisticRegressionMethod,
        },
    ),
}


def get_benchmark(slug: str) -> BenchmarkDefinition:
    if slug not in BENCHMARKS:
        raise KeyError(f"No benchmark registered for slug {slug!r}")
    return BENCHMARKS[slug]
