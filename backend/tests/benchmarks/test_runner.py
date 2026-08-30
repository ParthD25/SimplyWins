"""End-to-end runner behaviour and the provenance a run must carry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.benchmarks.evaluation import METRIC_DEFINITION_VERSION
from app.benchmarks.runner import load_dataset, publish_run, run_method

SLUG = "spam-detection"


@pytest.fixture(scope="module")
def rules_run(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("runs")
    return run_method(SLUG, "rules", runs_root=root), root


def test_dataset_loads_with_disjoint_splits() -> None:
    train, test, reference = load_dataset(SLUG)

    assert train and test
    assert reference.total_examples == len(train) + len(test)
    assert len(reference.sha256) == 64


def test_unknown_problem_is_rejected() -> None:
    with pytest.raises(KeyError):
        run_method("no-such-problem", "rules")


def test_unknown_method_is_rejected() -> None:
    with pytest.raises(KeyError, match="not registered"):
        run_method(SLUG, "ticket-frontier")


def test_run_scores_every_test_example(rules_run) -> None:
    record, _ = rules_run
    _, test, _ = load_dataset(SLUG)

    assert record.sample_count == len(test)
    assert 0.0 <= record.accuracy <= 100.0
    assert record.correct == round(record.accuracy / 100 * record.sample_count)


def test_run_beats_chance(rules_run) -> None:
    """Five balanced classes put chance at 20%. A method at chance means the
    harness is broken, not that the method is weak."""
    record, _ = rules_run

    assert record.accuracy > 40.0


def test_run_carries_required_provenance(rules_run) -> None:
    """Section 4 of PROJECT_STANDARD.md, asserted field by field."""
    record, _ = rules_run

    assert record.problem_slug == SLUG
    assert record.benchmark_definition_version
    assert record.dataset.name and record.dataset.version and record.dataset.sha256
    assert record.dataset.license and record.dataset.provenance
    assert record.code_commit_sha
    assert record.method_id and record.implementation_version
    assert record.complexity_rank >= 1
    assert record.runtime["python"]
    assert record.started_at.endswith("+00:00"), "timestamps must be UTC"
    assert record.seed is not None
    assert record.sample_count > 0
    assert record.metric_definition and record.metric_definition_version
    assert record.latency_definition
    assert record.raw_artifact_uri


def test_metric_definition_version_is_recorded(rules_run) -> None:
    record, _ = rules_run

    assert record.metric_definition_version == METRIC_DEFINITION_VERSION


def test_measured_and_estimated_states_are_distinguished(rules_run) -> None:
    """Cost is derived from an assumption, so it cannot claim MEASURED."""
    record, _ = rules_run

    assert record.result_state == "MEASURED"
    assert record.cost_state == "ESTIMATED"
    assert record.cost_model["source"]
    assert record.cost_model["as_of"]


def test_limitations_are_recorded(rules_run) -> None:
    record, _ = rules_run

    assert record.limitations
    assert any("synthetic" in item.lower() for item in record.limitations)


def test_raw_predictions_are_written_before_aggregation(rules_run) -> None:
    """A published score must be recomputable from the artifact."""
    record, root = rules_run
    artifact = root / record.run_id / "predictions.jsonl"
    rows = [json.loads(line) for line in artifact.read_text().splitlines()]

    assert len(rows) == record.sample_count
    recomputed = 100.0 * sum(row["correct"] for row in rows) / len(rows)
    assert recomputed == pytest.approx(record.accuracy, abs=0.0001)


def test_every_prediction_row_carries_its_latency(rules_run) -> None:
    record, root = rules_run
    rows = [
        json.loads(line)
        for line in (root / record.run_id / "predictions.jsonl").read_text().splitlines()
    ]

    assert all(row["latency_ns"] > 0 for row in rows)


def test_quality_metrics_reproduce_exactly(tmp_path: Path) -> None:
    """Accuracy must not drift between runs. Latency is excluded on purpose —
    it is wall-clock timing and varies by a few percent."""
    first = run_method(SLUG, "rules", runs_root=tmp_path / "a")
    second = run_method(SLUG, "rules", runs_root=tmp_path / "b")

    assert first.accuracy == second.accuracy
    assert first.macro_f1 == second.macro_f1
    assert first.correct == second.correct


def test_publish_copies_record_and_artifact(rules_run, tmp_path: Path) -> None:
    record, _ = rules_run

    destination = publish_run(record, published_root=tmp_path)

    assert (destination / f"{record.method_id}.run.json").is_file()
    payload = json.loads((destination / f"{record.method_id}.run.json").read_text())
    assert payload["accuracy"] == record.accuracy


def test_confusion_matrix_totals_match_the_sample_count(rules_run) -> None:
    record, _ = rules_run
    total = sum(sum(row.values()) for row in record.confusion.values())

    assert total == record.sample_count
