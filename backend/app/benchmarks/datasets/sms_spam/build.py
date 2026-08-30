"""Spam detection over the UCI SMS Spam Collection.

5,574 real SMS messages, hand-labelled ham or spam, collected for academic
research. Chosen because the messages are genuine consumer text nobody in this
project wrote, which is the whole point: a spam rule written here cannot have
planted the vocabulary it is later scored on.

Source: UCI Machine Learning Repository, "SMS Spam Collection" (Almeida,
Gómez Hidalgo & Yamakami, 2011). Released for research use; the repository's
citation policy asks that the source paper be cited, which DATASET.md does.
"""

from __future__ import annotations

import io
import zipfile
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

DATASET_NAME = "sms-spam"
DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"
SEED = 20260830
TRAIN_FRACTION = 0.7
LABELS = ("ham", "spam")

DATA_DIR = Path(__file__).resolve().parent / "data"
DATASET_PATH = DATA_DIR / f"{DATASET_NAME}.v{DATASET_VERSION}.jsonl"

SOURCE = SourceRef(
    name="UCI SMS Spam Collection",
    url="https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
    license_name="UCI ML Repository — research use, citation requested",
    license_url="https://archive.ics.uci.edu/dataset/228/sms+spam+collection",
    retrieved_note="Downloaded from the UCI static archive endpoint.",
)


def _parse(raw: bytes) -> list[LabelledRow]:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = next(n for n in archive.namelist() if n.endswith("SMSSpamCollection"))
        text = archive.read(name).decode("utf-8", errors="replace")

    rows: list[LabelledRow] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        label, _, message = line.partition("\t")
        label = label.strip().lower()
        message = normalise_whitespace(message)
        if label not in LABELS or not message:
            continue
        rows.append(LabelledRow(example_id=f"sms-{index:05d}", text=message, label=label))
    return rows


def build() -> dict[str, object]:
    archive = download(SOURCE.url, "sms-spam-collection.zip")
    rows = deduplicate(_parse(archive.read_bytes()))
    train, test = stratified_split(rows, seed=SEED, train_fraction=TRAIN_FRACTION)
    checksum = write_jsonl(DATASET_PATH, train, test)
    write_dataset_card(
        DATASET_PATH.parent.parent / "DATASET.md",
        title="SMS Spam Detection",
        source=SOURCE,
        dataset_name=DATASET_NAME,
        version=DATASET_VERSION,
        seed=SEED,
        train_fraction=TRAIN_FRACTION,
        checksum=checksum,
        train=train,
        test=test,
        task="Decide whether a single SMS message is unsolicited spam.",
        limitations=(
            (
                "Collected around 2011 from UK sources. Spam vocabulary and formatting "
                "have moved on, so a method's score here is not its score on today's "
                "traffic."
            ),
            (
                "Heavily imbalanced towards ham, which is realistic but means accuracy "
                "alone flatters a method that under-predicts spam. Macro F1 is reported "
                "alongside for that reason."
            ),
            ("SMS is short. Nothing here says how a method behaves on longer documents."),
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
