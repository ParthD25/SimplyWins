"""Command line entry point for the benchmark runner.

python -m app.benchmarks.cli run support-ticket-routing
python -m app.benchmarks.cli run support-ticket-routing --method ticket-rules
python -m app.benchmarks.cli list
"""

from __future__ import annotations

import argparse
import sys

from app.benchmarks.registry import BENCHMARKS
from app.benchmarks.runner import RunRecord, publish_run, run_all, run_method
from app.config import get_settings
from app.logging_config import configure_logging


def _print_table(records: list[RunRecord]) -> None:
    header = (
        f"{'method':<16} {'class':<16} {'accuracy':>9} {'macro F1':>9} "
        f"{'p50':>8} {'p95':>8} {'$/1K':>9}"
    )
    print()
    print(header)
    print("-" * len(header))
    for record in sorted(records, key=lambda item: item.complexity_rank):
        print(
            f"{record.method_id:<16} {record.method_class:<16} "
            f"{record.accuracy:>8.2f}% {record.macro_f1:>8.2f}% "
            f"{record.latency_p50_ms:>7.3f}ms {record.latency_p95_ms:>7.3f}ms "
            f"{record.cost_per_1k_usd:>9.5f}"
        )
    print()
    print(f"accuracy/latency: MEASURED · cost: ESTIMATED · n={records[0].sample_count}")
    print(
        f"dataset: {records[0].dataset.name} v{records[0].dataset.version} "
        f"(sha256 {records[0].dataset.sha256[:12]}…)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered benchmarks and methods")

    run_parser = subparsers.add_parser("run", help="Run a benchmark")
    run_parser.add_argument("slug", help="Problem slug, e.g. support-ticket-routing")
    run_parser.add_argument("--method", help="Run a single method instead of all")
    run_parser.add_argument("--seed", type=int, default=20260830)
    run_parser.add_argument(
        "--publish",
        action="store_true",
        help="Copy each run into benchmarks/published/ as the citable record",
    )

    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)

    if args.command == "list":
        for slug, definition in BENCHMARKS.items():
            print(f"{slug}  (definition v{definition.definition_version})")
            for method_id in definition.methods:
                print(f"    {method_id}")
        return 0

    try:
        if args.method:
            records = [run_method(args.slug, args.method, seed=args.seed)]
        else:
            records = run_all(args.slug, seed=args.seed)
    except (KeyError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if getattr(args, "publish", False):
        for record in records:
            destination = publish_run(record)
            print(f"published {record.method_id} -> {destination}")

    _print_table(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
