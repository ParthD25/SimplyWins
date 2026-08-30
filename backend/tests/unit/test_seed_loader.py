"""Integrity checks on the versioned seed definitions.

The seed file is now the backend's source of truth for problem definitions, so
malformed or self-inconsistent data should fail here rather than surface as a
wrong recommendation later.
"""

from __future__ import annotations

import re

import pytest

from app.config import DEFAULT_SEED_VERSION
from app.seed.loader import load_seed_file

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPECTED_METHOD_CLASSES = {"rules", "traditional-ml", "small-model", "frontier-llm"}


@pytest.fixture(scope="module")
def seed():
    return load_seed_file(DEFAULT_SEED_VERSION)


def test_seed_file_declares_its_version_and_data_state(seed) -> None:
    assert seed.seed_version
    # v2 carries promoted measured results alongside illustrative ones.
    assert seed.data_state in {"DEMO", "MEASURED", "MIXED"}
    assert "measured" in seed.notice.lower()


def test_seed_contains_the_six_mvp_problems(seed) -> None:
    assert len(seed.problems) == 6


def test_slugs_are_unique_and_kebab_case(seed) -> None:
    slugs = [problem.slug for problem in seed.problems]

    assert len(set(slugs)) == len(slugs)
    for slug in slugs:
        assert SLUG_PATTERN.match(slug), f"{slug} is not lowercase-kebab-case"


def test_every_problem_compares_the_four_method_classes(seed) -> None:
    """The MVP scope in docs/PRODUCT_SPEC.md requires all four classes."""
    for problem in seed.problems:
        classes = {method.method_class.value for method in problem.methods}
        assert classes == EXPECTED_METHOD_CLASSES, problem.slug


def test_complexity_ranks_are_unique_and_contiguous(seed) -> None:
    for problem in seed.problems:
        ranks = sorted(method.complexity_rank for method in problem.methods)
        assert ranks == [1, 2, 3, 4], problem.slug


def test_complexity_rank_follows_the_default_method_class_order(seed) -> None:
    """Section 3 of the standard: an override needs a stored rationale, and no
    seeded problem claims one."""
    expected = {"rules": 1, "traditional-ml": 2, "small-model": 3, "frontier-llm": 4}
    for problem in seed.problems:
        for method in problem.methods:
            assert method.complexity_rank == expected[method.method_class.value], (
                f"{problem.slug}/{method.method_id}"
            )


def test_method_ids_are_unique_within_and_across_problems(seed) -> None:
    all_ids = [method.method_id for problem in seed.problems for method in problem.methods]

    assert len(set(all_ids)) == len(all_ids)


def test_provenance_matches_the_claimed_state(seed) -> None:
    """A MEASURED result must cite where it came from; a DEMO result must not
    pretend to. This is the assertion that stops a figure being relabelled
    without evidence behind it."""
    for problem in seed.problems:
        for method in problem.methods:
            result = method.result
            if result.result_state.value == "MEASURED":
                assert result.run_id, method.method_id
                assert result.raw_artifact_uri, method.method_id
                assert result.measured_at, method.method_id
                assert result.sample_count and result.sample_count > 0, method.method_id
            else:
                assert result.raw_artifact_uri is None, method.method_id
                assert result.measured_at is None, method.method_id
                assert result.run_id is None, method.method_id


def test_a_measured_problem_cites_a_checksummed_dataset(seed) -> None:
    for problem in seed.problems:
        measured = [m for m in problem.methods if m.result.result_state.value == "MEASURED"]
        if measured:
            assert problem.dataset.sha256, problem.slug
            assert problem.dataset.license, problem.slug
            assert len(problem.dataset.sha256) == 64


def test_problem_status_is_measured_only_when_every_method_is(seed) -> None:
    for problem in seed.problems:
        states = {m.result.result_state.value for m in problem.methods}
        expected = "MEASURED" if states == {"MEASURED"} else "DEMO"
        assert problem.status.upper() == expected, problem.slug


def test_cost_is_never_claimed_as_measured(seed) -> None:
    """Cost is projected from latency plus an assumption, so it is at best
    ESTIMATED even when the result beside it is MEASURED."""
    for problem in seed.problems:
        for method in problem.methods:
            assert method.result.cost_state.value != "MEASURED", method.method_id


def test_metric_values_are_within_plausible_bounds(seed) -> None:
    for problem in seed.problems:
        for method in problem.methods:
            result = method.result
            assert 0 <= result.accuracy <= 100, method.method_id
            assert result.latency_p50_ms >= 0
            assert result.cost_per_1k >= 0


def test_non_deterministic_methods_are_not_claimed_auditable(seed) -> None:
    """Auditability is what the standard's auditability constraint filters on;
    a non-deterministic method must not claim it."""
    for problem in seed.problems:
        for method in problem.methods:
            if not method.result.deterministic:
                assert not method.result.auditable, method.method_id


def test_default_requirements_are_internally_consistent(seed) -> None:
    for problem in seed.problems:
        requirements = problem.default_requirements
        assert 0 < requirements.min_accuracy <= 100, problem.slug
        assert requirements.max_latency_ms > 0
        assert requirements.monthly_volume > 0


def test_missing_seed_version_raises(seed) -> None:
    with pytest.raises(FileNotFoundError):
        load_seed_file("v-does-not-exist")
