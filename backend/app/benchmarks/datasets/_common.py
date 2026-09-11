"""Shared machinery for datasets built from real, publicly published corpora.

Every benchmark dataset in this project is downloaded from a named public
source rather than generated here. That is a deliberate correction: an earlier
version of this benchmark used synthetic text written in this repository, and
the deterministic baseline was then written by the same author. Measured
against that data the rules method scored 78.9%, but an ablation showed the
entire score came from keywords that also appeared in the generator's own
templates — the same vocabulary on both sides of the experiment. Restricted to
terms the generator had never used, it scored 25.3% against a 20% floor.

The benchmark was measuring its author, not the methods. Real corpora remove
that failure mode at the root: nobody writing a method here chose the words in
the test set.
"""

from __future__ import annotations

import hashlib
import json
import random
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / ".cache"
# A plain identifying agent; some public data hosts reject the urllib default.
USER_AGENT = "SimplyWins-benchmark/1.0 (+https://github.com/ParthD25/SimplyWins)"


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Where a corpus came from, recorded so a reader can fetch it themselves."""

    name: str
    url: str
    license_name: str
    license_url: str
    retrieved_note: str


@dataclass(frozen=True, slots=True)
class LabelledRow:
    example_id: str
    text: str
    label: str


def download(url: str, filename: str, *, timeout: int = 300) -> Path:
    """Fetch ``url`` into the cache once, returning the local path.

    Cached so a rebuild does not re-hit a public data host, and so a run is
    reproducible offline once the corpus has been fetched.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / filename
    if target.exists() and target.stat().st_size > 0:
        return target

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        target.write_bytes(response.read())
    return target


def normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def stratified_split(
    rows: Sequence[LabelledRow], *, seed: int, train_fraction: float
) -> tuple[list[LabelledRow], list[LabelledRow]]:
    """Split per label, so both sides keep the corpus's class balance.

    Shuffled with an explicit seed rather than taken in file order: many public
    corpora are grouped by label or by collection date, and slicing such a file
    hands the two halves systematically different data.
    """
    by_label: dict[str, list[LabelledRow]] = defaultdict(list)
    for row in rows:
        by_label[row.label].append(row)

    rng = random.Random(seed)
    train: list[LabelledRow] = []
    test: list[LabelledRow] = []
    for label in sorted(by_label):
        bucket = sorted(by_label[label], key=lambda r: r.example_id)
        rng.shuffle(bucket)
        cut = int(len(bucket) * train_fraction)
        train.extend(bucket[:cut])
        test.extend(bucket[cut:])

    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def deduplicate(rows: Iterable[LabelledRow]) -> list[LabelledRow]:
    """Drop exact duplicate texts.

    A corpus with the same text in train and test inflates every method that
    can memorise, and public complaint and review corpora do contain repeats.
    """
    seen: set[str] = set()
    unique: list[LabelledRow] = []
    for row in rows:
        key = row.text.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def write_jsonl(path: Path, train: Sequence[LabelledRow], test: Sequence[LabelledRow]) -> str:
    """Write the split corpus and return its sha256.

    Sorted and separator-normalised so the checksum depends on the data alone,
    not on dict ordering or the writing machine.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "example_id": row.example_id,
                "text": row.text,
                "label": row.label,
                "split": split,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for split, rows in (("train", train), ("test", test))
        for row in rows
    ]
    payload = "\n".join(lines) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def label_counts(rows: Sequence[LabelledRow]) -> dict[str, int]:
    return dict(sorted(Counter(row.label for row in rows).items()))


def write_dataset_card(
    path: Path,
    *,
    title: str,
    source: SourceRef,
    dataset_name: str,
    version: str,
    seed: int,
    train_fraction: float,
    checksum: str,
    train: Sequence[LabelledRow],
    test: Sequence[LabelledRow],
    task: str,
    limitations: Sequence[str],
) -> None:
    """Write the dataset card from the built corpus.

    Generated rather than hand-written so the counts in the card cannot drift
    away from the file they describe — the previous card claimed properties the
    data no longer had.
    """
    train_counts = label_counts(train)
    test_counts = label_counts(test)
    labels = sorted(set(train_counts) | set(test_counts))
    total = len(train) + len(test)
    chance = 100.0 / len(labels) if labels else 0.0
    majority = max(test_counts.values()) / len(test) * 100.0 if test else 0.0

    rows = "\n".join(
        f"| `{label}` | {train_counts.get(label, 0)} | {test_counts.get(label, 0)} |"
        for label in labels
    )
    limitation_lines = "\n".join(f"- {item}" for item in limitations)

    path.write_text(
        f"""# {title}

{task}

**This corpus was not written for this project.** It is downloaded from a
public source, so no method benchmarked against it was written by the same
person who wrote the text it is scored on.

## Source

| | |
| --- | --- |
| Name | {source.name} |
| URL | {source.url} |
| License / terms | [{source.license_name}]({source.license_url}) |
| How it was taken | {source.retrieved_note} |

## Build

| | |
| --- | --- |
| Dataset id | `{dataset_name}` v{version} |
| sha256 | `{checksum}` |
| Split seed | {seed} |
| Train fraction | {train_fraction:g} |
| Total examples | {total} |
| Train / test | {len(train)} / {len(test)} |

Exact duplicate texts are removed before splitting, and the split is stratified
per label, so both halves keep the corpus's class balance.

## Labels

| Label | Train | Test |
| --- | ---: | ---: |
{rows}

## Floors a result must beat

| Baseline | Accuracy |
| --- | ---: |
| Uniform chance ({len(labels)} labels) | {chance:.2f}% |
| Always guess the most common test label | {majority:.2f}% |

A method scoring at or below these is not doing the task. Every benchmark run
recomputes both and stores them beside the result.

## Limitations

{limitation_lines}

---

*Generated by the dataset builder. Rebuild with*
*`python -m {path.parent.name and "app.benchmarks.datasets." + path.parent.name + ".build"}`.*
""",
        encoding="utf-8",
    )
