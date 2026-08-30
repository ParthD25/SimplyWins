"""Support-request routing over real CFPB consumer complaint narratives.

This replaces a synthetic corpus that was written in this repository. The
narratives here are written by members of the public to the Consumer Financial
Protection Bureau, and the product category each was filed under is the routing
label — a real "which queue does this belong in?" decision, made by someone
other than the author of any method scored on it.

Text is as submitted, including the Bureau's ``XXXX`` redactions of personal
information. Those are left in place: they are a genuine property of the
corpus, and stripping them would make the task easier than the real one.

Source: CFPB Consumer Complaint Database public API. The Bureau publishes the
database as a public record; complaints are published with consent and after
redaction.
"""

from __future__ import annotations

import json
import urllib.parse
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

DATASET_NAME = "cfpb-complaint-routing"
DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"
SEED = 20260830
TRAIN_FRACTION = 0.7
PER_LABEL = 900
MIN_CHARS = 120
MAX_CHARS = 2000

DATA_DIR = Path(__file__).resolve().parent / "data"
DATASET_PATH = DATA_DIR / f"{DATASET_NAME}.v{DATASET_VERSION}.jsonl"

API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"

# The Bureau's product taxonomy is finer than a routing queue needs and its
# names have changed over time. These are the queues; the values are the
# official product strings folded into each.
QUEUES: dict[str, tuple[str, ...]] = {
    "credit-reporting": (
        "Credit reporting, credit repair services, or other personal consumer reports",
    ),
    "debt-collection": ("Debt collection",),
    "mortgage": ("Mortgage",),
    "cards": ("Credit card or prepaid card",),
    "bank-account": ("Checking or savings account",),
    "loans": ("Student loan", "Vehicle loan or lease", "Payday loan, title loan, or personal loan"),
    "money-transfer": ("Money transfer, virtual currency, or money service",),
}
LABELS = tuple(sorted(QUEUES))

SOURCE = SourceRef(
    name="CFPB Consumer Complaint Database",
    url="https://www.consumerfinance.gov/data-research/consumer-complaints/",
    license_name="US Government public record (public domain)",
    license_url="https://www.consumerfinance.gov/data-research/consumer-complaints/",
    retrieved_note=(
        f"Sampled via the public search API, up to {PER_LABEL} narratives per queue, "
        f"restricted to complaints with a consumer narrative of "
        f"{MIN_CHARS}-{MAX_CHARS} characters."
    ),
)


def _fetch_product(product: str, size: int) -> list[dict[str, object]]:
    query = urllib.parse.urlencode(
        {
            "size": size,
            "no_aggs": "true",
            "has_narrative": "true",
            "field": "complaint_what_happened",
            "product": product,
        }
    )
    filename = "cfpb-" + urllib.parse.quote_plus(product)[:60] + f"-{size}.json"
    path = download(f"{API}?{query}", filename)
    payload = json.loads(path.read_text(encoding="utf-8"))
    hits = payload.get("hits", {}).get("hits", [])
    return [hit.get("_source", {}) for hit in hits]


def build() -> dict[str, object]:
    rows: list[LabelledRow] = []
    for queue in LABELS:
        products = QUEUES[queue]
        # Split the per-queue quota across the products folded into it, so a
        # queue built from three products is not three times the size.
        per_product = max(1, PER_LABEL // len(products))
        collected: list[LabelledRow] = []
        for product in products:
            for source in _fetch_product(product, per_product):
                text = normalise_whitespace(str(source.get("complaint_what_happened") or ""))
                if not (MIN_CHARS <= len(text) <= MAX_CHARS):
                    continue
                complaint_id = str(source.get("complaint_id") or len(collected))
                collected.append(
                    LabelledRow(example_id=f"cfpb-{complaint_id}", text=text, label=queue)
                )
        rows.extend(collected)

    rows = deduplicate(rows)

    # Trim every queue to the smallest one. A method can otherwise score well by
    # always guessing the largest class, which measures the sampler, not the method.
    counts = label_counts(rows)
    floor = min(counts.values())
    balanced: list[LabelledRow] = []
    seen: dict[str, int] = dict.fromkeys(LABELS, 0)
    for row in sorted(rows, key=lambda r: r.example_id):
        if seen[row.label] < floor:
            balanced.append(row)
            seen[row.label] += 1

    train, test = stratified_split(balanced, seed=SEED, train_fraction=TRAIN_FRACTION)
    checksum = write_jsonl(DATASET_PATH, train, test)
    write_dataset_card(
        DATASET_PATH.parent.parent / "DATASET.md",
        title="Consumer Complaint Routing (CFPB)",
        source=SOURCE,
        dataset_name=DATASET_NAME,
        version=DATASET_VERSION,
        seed=SEED,
        train_fraction=TRAIN_FRACTION,
        checksum=checksum,
        train=train,
        test=test,
        task="Route a consumer finance complaint to the team that handles that product.",
        limitations=(
            (
                "The label is the product category the complaint was filed under, which "
                "is not always the category a reader would choose. One sampled complaint "
                "about a maturing certificate of deposit is filed under money transfer. "
                "That noise is real and caps how high any method can score."
            ),
            (
                "Narratives are published with the Bureau's redactions in place, so "
                "personal details appear as XXXX. Left as-is, because removing them would "
                "make the task easier than the real one."
            ),
            (
                "Only complaints that include a narrative are published, and consumers "
                "opt in to that. Complaints with narratives are not a random sample of "
                "all complaints."
            ),
            (
                "Queues were balanced by trimming every category to the smallest, so this "
                "does not reflect real queue volumes."
            ),
            (
                "Sampled from the API's default ordering rather than across the full "
                "3.8M-row database, so it is a slice, not a representative draw."
            ),
        ),
    )
    return {
        "dataset": DATASET_NAME,
        "version": DATASET_VERSION,
        "checksum": checksum,
        "raw_before_balance": counts,
        "per_queue_after_balance": floor,
        "train": len(train),
        "test": len(test),
        "train_labels": label_counts(train),
        "test_labels": label_counts(test),
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
