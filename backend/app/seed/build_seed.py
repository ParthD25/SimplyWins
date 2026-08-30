"""Builds the served seed from published benchmark runs.

Seed files are the backend's source of truth, so every figure in one has to
arrive by a reproducible path rather than by hand-editing JSON. This reads
``benchmarks/published/<slug>/<method>.run.json`` and writes a seed version
whose measured figures are copied from those records verbatim.

Methods that exist in the registry but have never been run are still written
out, marked ``NOT_RUN`` and carrying no figures. Omitting them would be the
more flattering choice and the wrong one: the evidence rule turns on whether
*every* method in the comparison set has been measured, so dropping the unrun
ones would let a benchmark with two of four methods measured name a winner.

Usage: ``python -m app.seed.build_seed --to v3``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.benchmarks.registry import BENCHMARKS

SEED_ROOT = Path(__file__).resolve().parent
PUBLISHED_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "published"

# Editorial framing per problem: the decision a reader is actually making, and
# the operating requirements that decision is made against. These are product
# judgements, not measurements, so they live here rather than in a run record.
PROBLEMS: dict[str, dict[str, Any]] = {
    "support-request-routing": {
        "title": "Support Request Routing",
        "category": "Classification",
        "description": (
            "Route an incoming consumer finance complaint to the team that "
            "handles that product, across seven queues."
        ),
        "decision_question": (
            "Can keyword rules route real complaints well enough, or does this "
            "job need a trained model?"
        ),
        "default_requirements": {
            "min_accuracy": 85,
            "max_latency_ms": 500,
            "auditability_required": True,
            "monthly_volume": 250000,
        },
        "rationale": (
            "Misrouting sends a complaint to a team that cannot resolve it, so "
            "the cost of an error is a delay rather than a wrong answer. "
            "Auditability is required because a routing decision has to be "
            "explainable to the team that receives it."
        ),
    },
    "spam-detection": {
        "title": "Spam Detection",
        "category": "Classification",
        "description": "Decide whether an inbound SMS message is unsolicited spam.",
        "decision_question": (
            "Spam filtering is the oldest text-classification job there is. "
            "Does it need a language model?"
        ),
        "default_requirements": {
            "min_accuracy": 95,
            "max_latency_ms": 100,
            "auditability_required": True,
            "monthly_volume": 5000000,
        },
        "rationale": (
            "Volume is enormous and per-message value is near zero, so cost per "
            "item dominates. A false positive hides a real message from someone, "
            "which is why the accuracy bar is high and auditability is required."
        ),
    },
    "sentiment-classification": {
        "title": "Sentiment Classification",
        "category": "Classification",
        "description": ("Judge whether a sentence from a film review is positive or negative."),
        "decision_question": ("Sentiment is the canonical 'just use an LLM' task. Is it?"),
        "default_requirements": {
            "min_accuracy": 90,
            "max_latency_ms": 1000,
            "auditability_required": False,
            "monthly_volume": 100000,
        },
        "rationale": (
            "Sentiment feeds dashboards rather than decisions about individuals, "
            "so an error is cheap and auditability is not required. That makes it "
            "the fairest test of whether a language model earns its cost."
        ),
    },
}


def _load_run(slug: str, method_id: str) -> dict[str, Any] | None:
    path = PUBLISHED_ROOT / slug / f"{method_id}.run.json"
    if not path.is_file():
        return None
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _method_entry(slug: str, method_id: str, factory: Any) -> dict[str, Any]:
    metadata = factory().metadata()
    run = _load_run(slug, method_id)

    if run is None:
        # No figures at all. Zeroes are placeholders the UI must not render as
        # a result, which is what NOT_RUN marks.
        result = {
            "result_state": "NOT_RUN",
            "cost_state": "NOT_RUN",
            "accuracy": 0.0,
            "latency_p50_ms": 0.0,
            "cost_per_1k": 0.0,
            "deterministic": metadata.deterministic,
            "auditable": metadata.auditable,
            "sample_count": 0,
            "run_id": None,
            "raw_artifact_uri": None,
            "measured_at": None,
            "metric_definition_version": None,
        }
    else:
        result = {
            "result_state": run["result_state"],
            "cost_state": run["cost_state"],
            "accuracy": run["accuracy"],
            "latency_p50_ms": run["latency_p50_ms"],
            "cost_per_1k": run["cost_per_1k_usd"],
            "deterministic": run["deterministic"],
            "auditable": run["auditable"],
            "sample_count": run["sample_count"],
            "run_id": run["run_id"],
            "raw_artifact_uri": run["raw_artifact_uri"],
            "measured_at": run["completed_at"],
            "metric_definition_version": run["metric_definition_version"],
            "leakage_audit": run.get("leakage_audit"),
        }

    return {
        "method_id": method_id,
        "name": metadata.name,
        "short_name": metadata.short_name,
        "method_class": metadata.method_class,
        "complexity_rank": metadata.complexity_rank,
        "implementation_version": metadata.implementation_version,
        "provider": metadata.provider,
        "model_name": metadata.model_name,
        "model_version": metadata.model_version,
        "notes": metadata.notes,
        "result": result,
    }


def build() -> dict[str, Any]:
    problems: list[dict[str, Any]] = []
    for slug, definition in BENCHMARKS.items():
        editorial = PROBLEMS[slug]
        methods = [
            _method_entry(slug, method_id, factory)
            for method_id, factory in definition.methods.items()
        ]
        methods.sort(key=lambda m: m["complexity_rank"])

        # Dataset provenance is copied from whichever run record exists, so the
        # seed cannot describe a different corpus than the one measured.
        reference = next(
            (
                _load_run(slug, m["method_id"])
                for m in methods
                if _load_run(slug, m["method_id"]) is not None
            ),
            None,
        )
        dataset = (reference or {}).get("dataset", {})

        measured = sum(1 for m in methods if m["result"]["result_state"] == "MEASURED")
        problems.append(
            {
                "slug": slug,
                "title": editorial["title"],
                "category": editorial["category"],
                "description": editorial["description"],
                "decision_question": editorial["decision_question"],
                "rationale": editorial["rationale"],
                "default_requirements": editorial["default_requirements"],
                "benchmark_definition_version": definition.definition_version,
                "status": "MEASURED" if measured == len(methods) else "PARTIAL",
                "dataset": {
                    "name": dataset.get("name"),
                    "version": dataset.get("version"),
                    "sha256": dataset.get("sha256"),
                    "license": dataset.get("license"),
                    "source_url": None,
                    "provenance_notes": dataset.get("provenance"),
                    "sample_count_label": (
                        f"{dataset.get('total_examples', 0):,} examples" if dataset else None
                    ),
                },
                "methods": methods,
            }
        )
    total = sum(len(p["methods"]) for p in problems)
    measured = sum(
        1 for p in problems for m in p["methods"] if m["result"]["result_state"] == "MEASURED"
    )
    return {
        "seed_version": "3.0.0",
        "data_state": "MEASURED" if measured == total else "MIXED",
        "notice": (
            f"{measured} of {total} methods are MEASURED against a real, publicly "
            "published corpus, each citing its run id and dataset checksum. The "
            "remaining methods are hosted models that have never been run and are "
            "marked NOT_RUN: they carry no figures, and their placeholder zeroes "
            "are not results. Per section 3.1 of PROJECT_STANDARD.md a problem "
            "produces no recommendation until every one of its methods has been "
            "measured, so no problem here names a winner."
        ),
        "problems": problems,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", default="v3", help="Seed version directory to write")
    args = parser.parse_args()

    payload = build()
    target = SEED_ROOT / args.to / "problems.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for problem in payload["problems"]:
        states = [m["result"]["result_state"] for m in problem["methods"]]
        measured = states.count("MEASURED")
        print(f"{problem['slug']:28} {measured}/{len(states)} measured  {states}")
    print(f"\nWrote {target}")


if __name__ == "__main__":
    main()
