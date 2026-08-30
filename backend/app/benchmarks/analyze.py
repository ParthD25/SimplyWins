"""Reports the statistics behind a benchmark's headline numbers.

Usage: ``python -m app.benchmarks.analyze [problem-slug]``
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from app.benchmarks.analysis import (
    accuracy_by_length,
    confusion_pairs,
    fallback_rate,
    load_predictions,
    mcnemar,
    paired_bootstrap,
    per_class,
    prior_bias,
    project_errors,
    wilson_interval,
)
from app.benchmarks.registry import BENCHMARKS, get_benchmark

PUBLISHED = Path(__file__).resolve().parents[2] / "benchmarks" / "published"

# Which label each problem's rules baseline falls through to when its
# vocabulary matches nothing.
FALLBACKS = {
    "support-request-routing": "bank-account",
    "spam-detection": "ham",
    "sentiment-classification": "positive",
}


def _texts(slug: str) -> dict[str, str]:
    module = importlib.import_module(get_benchmark(slug).dataset_module)
    texts: dict[str, str] = {}
    for line in module.DATASET_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            texts[row["example_id"]] = row["text"]
    return texts


def _requirements(slug: str) -> int:
    """The problem's stated operating volume, from the served seed."""
    seed = json.loads(
        (Path(__file__).resolve().parents[1] / "seed" / "v3" / "problems.json").read_text(
            encoding="utf-8"
        )
    )
    for problem in seed["problems"]:
        if problem["slug"] == slug:
            return int(problem["default_requirements"]["monthly_volume"])
    return 0


def analyse(slug: str) -> None:
    directory = PUBLISHED / slug
    runs = sorted(directory.glob("*.predictions.jsonl"))
    if not runs:
        print(f"{slug}: no published predictions")
        return

    sets = {path.name.split(".")[0]: load_predictions(path) for path in runs}
    texts = _texts(slug)

    print("=" * 78)
    print(f"{slug}")
    print("=" * 78)

    labels = sorted({p.gold for rows in sets.values() for p in rows})
    n = len(next(iter(sets.values())))
    chance = 1 / len(labels)
    from collections import Counter

    gold_counts = Counter(p.gold for p in next(iter(sets.values())))
    majority = max(gold_counts.values()) / n

    print(f"\nEvaluation set: {n} examples, {len(labels)} labels")
    print(f"Chance: {chance * 100:.2f}%   Majority class: {majority * 100:.2f}%")

    # ---- Accuracy with uncertainty -------------------------------------
    print("\n-- Accuracy, 95% Wilson interval --")
    for method, rows in sets.items():
        correct = sum(1 for p in rows if p.correct)
        interval = wilson_interval(correct, len(rows))
        lift = interval.point - majority
        print(
            f"  {method:8} {interval}   "
            f"{correct}/{len(rows)}   lift over majority: {lift * 100:+.2f} pts"
        )

    # ---- Are they actually different? ----------------------------------
    if len(sets) == 2:
        (a_name, a_rows), (b_name, b_rows) = sorted(sets.items())
        result = mcnemar(a_rows, b_rows)
        boot = paired_bootstrap(a_rows, b_rows)
        print(f"\n-- {b_name} vs {a_name}: McNemar exact, paired --")
        print(
            f"  both correct {result.both_correct}   "
            f"only {a_name} {result.only_a}   only {b_name} {result.only_b}   "
            f"both wrong {result.both_wrong}"
        )
        print(f"  discordant pairs: {result.discordant}")
        print(f"  p = {result.p_value:.3e}")
        print(
            f"  accuracy difference ({b_name} - {a_name}): "
            f"{boot.point * 100:+.2f} pts, 95% bootstrap CI "
            f"[{boot.low * 100:+.2f}, {boot.high * 100:+.2f}]"
        )

    # ---- Per-class behaviour and bias ----------------------------------
    for method, rows in sets.items():
        metrics = per_class(rows)
        bias = prior_bias(metrics)
        print(f"\n-- {method}: per-class --")
        header = (
            f"  {'label':22} {'n':>5} {'pred':>6} {'prec':>7} "
            f"{'recall':>7} {'F1':>7} {'pred/true':>10}"
        )
        print(header)
        for entry in metrics:
            print(
                f"  {entry.label:22} {entry.support:5} {entry.predicted:6} "
                f"{entry.precision:7.3f} {entry.recall:7.3f} {entry.f1:7.3f} "
                f"{entry.prediction_ratio:10.2f}"
            )
        print(
            f"  prior bias: chi2 = {bias.chi_square:.1f} on {bias.degrees_of_freedom} df, "
            f"p = {bias.p_value:.3e}"
        )
        print(
            f"  most over-used: {bias.most_overused} ({bias.most_overused_ratio:.2f}x)   "
            f"most under-used: {bias.most_underused} ({bias.most_underused_ratio:.2f}x)"
        )

        fallback = FALLBACKS.get(slug)
        if method == "rules" and fallback:
            rate = fallback_rate(rows, fallback)
            print(f"  fell through to '{fallback}': {rate * 100:.1f}% of predictions")

        print("  top confusions (true -> predicted):")
        for gold, predicted, count in confusion_pairs(rows, top=4):
            print(f"    {gold} -> {predicted}: {count}")

        # The label whose false positives actually hurt, per problem.
        costly = {
            "spam-detection": "spam",
            "sentiment-classification": "negative",
        }.get(slug)
        if costly:
            requirements = _requirements(slug)
            projection = project_errors(
                metrics, costly, monthly_volume=requirements, sample_size=len(rows)
            )
            print(
                f"  at {requirements:,}/month, predicting '{costly}': "
                f"{projection.false_positives:,.0f} false positives "
                f"({projection.false_positive_rate * 100:.2f}% of true negatives), "
                f"{projection.false_negatives:,.0f} missed"
            )

        strata = accuracy_by_length(rows, texts)
        if strata:
            print("  accuracy by input length:")
            for label, size, interval in strata:
                print(f"    {label:24} n={size:5}  {interval}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", nargs="?", help="Problem slug; omit for all")
    args = parser.parse_args()

    slugs = [args.slug] if args.slug else list(BENCHMARKS)
    for slug in slugs:
        analyse(slug)
        print()


if __name__ == "__main__":
    main()
