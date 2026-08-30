"""Promote published benchmark runs into a new versioned seed.

Seed files are the backend's source of truth, so measured numbers must reach
them by a reproducible path rather than by hand-editing JSON. This reads the
published run records for a problem and writes the next seed version with those
methods marked ``MEASURED`` and carrying their run provenance.

    python -m app.seed.promote --from v1 --to v2

Methods with no published run keep their existing ``DEMO`` figures, which is why
a promoted problem can sit at "2 of 4 measured": the evidence rule then declines
to recommend anything for it until the rest are run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SEED_ROOT = Path(__file__).parent
PUBLISHED_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "published"


def load_published(slug: str) -> dict[str, dict[str, Any]]:
    """Published run records for a problem, keyed by method id."""
    directory = PUBLISHED_ROOT / slug
    if not directory.is_dir():
        return {}
    runs: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.run.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        runs[record["method_id"]] = record
    return runs


def _promote_method(method: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Replace one method's illustrative figures with its measured ones."""
    result = dict(method["result"])
    result.update(
        {
            "result_state": run["result_state"],
            "accuracy": run["accuracy"],
            # Kept at full precision: these methods are genuinely sub-millisecond.
            "latency_p50_ms": run["latency_p50_ms"],
            "cost_per_1k": run["cost_per_1k_usd"],
            "metric_definition_version": run["metric_definition_version"],
            "raw_artifact_uri": run["raw_artifact_uri"],
            "measured_at": run["completed_at"],
            # Cost is projected from measured latency plus a dated rate, so it
            # carries its own weaker state alongside the measured result.
            "cost_state": run["cost_state"],
            "run_id": run["run_id"],
            "sample_count": run["sample_count"],
        }
    )
    promoted = dict(method)
    promoted["result"] = result
    promoted["implementation_version"] = run["implementation_version"]
    return promoted


def promote(source_version: str, target_version: str) -> tuple[Path, int, int]:
    source = SEED_ROOT / source_version / "problems.json"
    if not source.is_file():
        raise FileNotFoundError(f"No seed at {source}")
    seed = json.loads(source.read_text(encoding="utf-8"))

    promoted_methods = 0
    promoted_problems = 0
    for problem in seed["problems"]:
        runs = load_published(problem["slug"])
        if not runs:
            continue
        promoted_problems += 1
        methods = []
        for method in problem["methods"]:
            run = runs.get(method["method_id"])
            if run is None:
                methods.append(method)
                continue
            methods.append(_promote_method(method, run))
            promoted_methods += 1
        problem["methods"] = methods

        # The dataset a measured run actually used replaces the placeholder.
        any_run = next(iter(runs.values()))
        dataset = any_run["dataset"]
        problem["dataset"] = {
            "name": dataset["name"],
            "version": dataset["version"],
            "sample_count_label": f"{dataset['total_examples']:,} examples",
            "sha256": dataset["sha256"],
            "license": dataset["license"],
            "source_url": None,
            "provenance_notes": dataset["provenance"],
        }
        problem["benchmark_definition_version"] = any_run["benchmark_definition_version"]
        measured = sum(1 for m in problem["methods"] if m["result"]["result_state"] == "MEASURED")
        # A problem is only MEASURED once every method in its set is.
        problem["status"] = "MEASURED" if measured == len(problem["methods"]) else "DEMO"

    seed["seed_version"] = target_version.lstrip("v") + ".0.0"
    states = {
        method["result"]["result_state"]
        for problem in seed["problems"]
        for method in problem["methods"]
    }
    seed["data_state"] = "MIXED" if len(states) > 1 else states.pop()
    seed["notice"] = (
        "Mixed provenance. Methods marked MEASURED carry results from a reproducible "
        "benchmark run and cite their run id and dataset checksum. Methods marked DEMO "
        "are illustrative and, per section 3.1 of PROJECT_STANDARD.md, cannot influence "
        "any recommendation. A problem produces no recommendation until every one of "
        "its methods has been measured."
    )

    target = SEED_ROOT / target_version
    target.mkdir(parents=True, exist_ok=True)
    destination = target / "problems.json"
    destination.write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination, promoted_problems, promoted_methods


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promote")
    parser.add_argument("--from", dest="source", default="v1")
    parser.add_argument("--to", dest="target", default="v2")
    args = parser.parse_args(argv)

    path, problems, methods = promote(args.source, args.target)
    print(f"wrote {path}")
    print(f"promoted {methods} method(s) across {problems} problem(s) to MEASURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
