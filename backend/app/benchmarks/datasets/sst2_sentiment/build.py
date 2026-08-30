"""Sentiment classification over SST-2 (Stanford Sentiment Treebank).

Real single-sentence movie reviews from Rotten Tomatoes with human polarity
labels — the standard academic benchmark for binary sentiment, and text written
by film critics rather than by anyone on this project.

Source: Socher et al. (2013), "Recursive Deep Models for Semantic
Compositionality over a Sentiment Treebank". Fetched from a public mirror of
the SST-2 sentence splits; the underlying treebank is distributed for research
use. The mirror is recorded here rather than hidden, because a reader checking
these numbers needs the exact file this was built from.
"""

from __future__ import annotations

from pathlib import Path

from app.benchmarks.datasets._common import (
    LabelledRow,
    SourceRef,
    deduplicate,
    download,
    label_counts,
    normalise_whitespace,
    stratified_split,
    write_dataset_card,
    write_jsonl,
)

DATASET_NAME = "sst2-sentiment"
DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"
SEED = 20260830
TRAIN_FRACTION = 0.7
LABELS = ("negative", "positive")

DATA_DIR = Path(__file__).resolve().parent / "data"
DATASET_PATH = DATA_DIR / f"{DATASET_NAME}.v{DATASET_VERSION}.jsonl"

_BASE = (
    "https://raw.githubusercontent.com/clairett/pytorch-sentiment-classification/master/data/SST2"
)
SPLIT_FILES = ("train.tsv", "dev.tsv", "test.tsv")

SOURCE = SourceRef(
    name="SST-2 (Stanford Sentiment Treebank, binary sentence splits)",
    url=f"{_BASE}/train.tsv",
    license_name="Research use (Socher et al., 2013)",
    license_url="https://nlp.stanford.edu/sentiment/",
    retrieved_note=(
        "train/dev/test TSVs pooled, then re-split here with this project's own "
        "seed so the split is reproducible from the recorded parameters alone."
    ),
)


def _parse(text: str, prefix: str) -> list[LabelledRow]:
    rows: list[LabelledRow] = []
    for index, line in enumerate(text.splitlines()):
        sentence, _, raw_label = line.rpartition("\t")
        sentence = normalise_whitespace(sentence)
        raw_label = raw_label.strip()
        if not sentence or raw_label not in {"0", "1"}:
            continue
        rows.append(
            LabelledRow(
                example_id=f"sst2-{prefix}-{index:05d}",
                text=sentence,
                label=LABELS[int(raw_label)],
            )
        )
    return rows


def build() -> dict[str, object]:
    rows: list[LabelledRow] = []
    for filename in SPLIT_FILES:
        path = download(f"{_BASE}/{filename}", f"sst2-{filename}")
        stem = filename.removesuffix(".tsv")
        rows.extend(_parse(path.read_text(encoding="utf-8", errors="replace"), stem))

    rows = deduplicate(rows)
    train, test = stratified_split(rows, seed=SEED, train_fraction=TRAIN_FRACTION)
    checksum = write_jsonl(DATASET_PATH, train, test)
    write_dataset_card(
        DATASET_PATH.parent.parent / "DATASET.md",
        title="Film Review Sentiment (SST-2)",
        source=SOURCE,
        dataset_name=DATASET_NAME,
        version=DATASET_VERSION,
        seed=SEED,
        train_fraction=TRAIN_FRACTION,
        checksum=checksum,
        train=train,
        test=test,
        task="Judge whether a single sentence from a film review is positive or negative.",
        limitations=(
            (
                "Film criticism, not product or support text. Sentiment vocabulary is "
                "domain-specific and these numbers do not transfer to other domains "
                "unexamined."
            ),
            (
                "Sentences were selected for the original treebank partly because they "
                "carry clear polarity, so this is easier than sentiment in the wild."
            ),
            (
                "Binary only: the neutral cases that make real sentiment work hard were "
                "removed upstream."
            ),
        ),
    )
    return {
        "dataset": DATASET_NAME,
        "version": DATASET_VERSION,
        "checksum": checksum,
        "train": len(train),
        "test": len(test),
        "train_labels": label_counts(train),
        "test_labels": label_counts(test),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build(), indent=2))
