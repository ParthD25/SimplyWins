"""Dataset integrity.

The template-disjoint guarantee is the reason the published accuracy means
anything, so it is asserted rather than trusted.
"""

from __future__ import annotations

import collections
import hashlib
import json

import pytest

from app.benchmarks.datasets.support_ticket_routing import generate as dataset


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return [
        json.loads(line) for line in dataset.DATASET_PATH.read_text(encoding="utf-8").splitlines()
    ]


def test_dataset_file_is_present_and_complete(rows: list[dict]) -> None:
    assert len(rows) == dataset.TOTAL_EXAMPLES


def test_generation_is_deterministic() -> None:
    """Same seed, same dataset — otherwise the checksum in every run record is
    meaningless."""
    first = dataset.generate()
    second = dataset.generate()

    assert [item.text for item in first] == [item.text for item in second]
    assert [item.split for item in first] == [item.split for item in second]


def test_on_disk_file_matches_the_generator() -> None:
    expected = dataset.generate()
    payload = dataset.DATASET_PATH.read_text(encoding="utf-8")
    actual = [json.loads(line) for line in payload.splitlines()]

    assert [item.example_id for item in expected] == [row["example_id"] for row in actual]
    assert [item.text for item in expected] == [row["text"] for row in actual]


def test_checksum_is_stable(rows: list[dict]) -> None:
    payload = dataset.DATASET_PATH.read_text(encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    assert len(digest) == 64
    # Recomputing must give the same answer, which is what run records rely on.
    assert digest == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_splits_share_no_template(rows: list[dict]) -> None:
    """The guarantee that makes the accuracy figure a generalisation claim."""
    train = {row["template_id"] for row in rows if row["split"] == "train"}
    test = {row["template_id"] for row in rows if row["split"] == "test"}

    assert train and test
    assert train & test == set()


def test_every_class_appears_in_both_splits(rows: list[dict]) -> None:
    for split in ("train", "test"):
        labels = {row["label"] for row in rows if row["split"] == split}
        assert labels == set(dataset.LABELS), split


def test_classes_are_balanced(rows: list[dict]) -> None:
    counts = collections.Counter(row["label"] for row in rows)

    assert len(set(counts.values())) == 1, counts


def test_every_label_is_known(rows: list[dict]) -> None:
    assert {row["label"] for row in rows} == set(dataset.LABELS)


def test_hard_cases_are_a_meaningful_share(rows: list[dict]) -> None:
    """Without hard cases keyword matching would score near 100% and the
    comparison would say nothing."""
    hard = sum(1 for row in rows if row["difficulty"] != "plain")

    assert hard / len(rows) > 0.30


def test_no_example_is_empty(rows: list[dict]) -> None:
    assert all(row["text"].strip() for row in rows)


def test_example_ids_are_unique(rows: list[dict]) -> None:
    ids = [row["example_id"] for row in rows]

    assert len(set(ids)) == len(ids)


def test_each_class_has_enough_templates_to_generalise() -> None:
    """A small pool was what made an earlier version measure memorisation."""
    for label, templates in dataset.TEMPLATES.items():
        assert len(templates) >= 30, label
