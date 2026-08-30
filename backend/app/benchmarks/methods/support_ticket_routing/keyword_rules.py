"""Keyword routing rules — the deterministic baseline.

Written the way a support team writes triage rules: a vocabulary per queue,
scored by how many terms a ticket hits, with a fixed priority order breaking
ties. Every decision is inspectable, which is what makes the method auditable.

The vocabulary is ordinary support-domain language, chosen without consulting
the dataset generator's phrasings. It is therefore a fair baseline rather than
a lookup table fitted to the data.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.benchmarks.base import CostModel, Example, MethodConfig, MethodMetadata

IMPLEMENTATION_VERSION = "1.0.0"
FALLBACK_LABEL = "other"

# Ordered by triage priority. When two queues score equally, the earlier queue
# wins — money and outages are escalated ahead of general enquiries.
KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "billing",
        (
            "invoice",
            "charge",
            "charged",
            "charging",
            "refund",
            "refunded",
            "payment",
            "billed",
            "billing",
            "bill",
            "price",
            "pricing",
            "subscription",
            "receipt",
            "tax",
            "paid",
            "unpaid",
            "overcharge",
            "credit card",
            "debit",
            "card",
            "statement",
            "purchase order",
            "downgrade",
            "annual",
            "discount",
            "cost",
        ),
    ),
    (
        "technical",
        (
            "error",
            "errored",
            "crash",
            "crashes",
            "crashing",
            "crashed",
            "bug",
            "broken",
            "not working",
            "stopped working",
            "timeout",
            "timeouts",
            "fails",
            "failing",
            "failed",
            "freeze",
            "freezes",
            "frozen",
            "slow",
            "spinning",
            "spins",
            "500",
            "502",
            "403",
            "api",
            "sync",
            "webhook",
            "stale",
            "empty file",
            "loading",
            "upload",
            "uploading",
            "export",
        ),
    ),
    (
        "account",
        (
            "log in",
            "login",
            "logging in",
            "log-in",
            "password",
            "sign in",
            "signin",
            "profile",
            "permission",
            "permissions",
            "admin",
            "two factor",
            "two-factor",
            "2fa",
            "authentication",
            "locked out",
            "role",
            "workspace",
            "email address",
            "username",
            "access",
            "owner",
            "ownership",
            "delete my data",
        ),
    ),
    (
        "shipping",
        (
            "delivery",
            "deliver",
            "delivered",
            "shipment",
            "shipping",
            "ship",
            "parcel",
            "package",
            "tracking",
            "tracked",
            "courier",
            "warehouse",
            "customs",
            "dispatch",
            "arrived",
            "arrive",
            "return",
            "exchange",
            "carrier",
            "delivery address",
            "order",
            "box",
        ),
    ),
)

# Longest-first so multi-word terms match before their component words.
_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (
        label,
        tuple(
            re.compile(rf"\b{re.escape(term)}\b") for term in sorted(terms, key=len, reverse=True)
        ),
    )
    for label, terms in KEYWORDS
)


class KeywordRulesMethod:
    """Scores each queue by keyword hits and routes to the highest."""

    def setup(self, config: MethodConfig) -> None:
        # Deterministic rules need no fitting; training data is ignored by design.
        return None

    def explain(self, text: str) -> dict[str, int]:
        """Per-queue hit counts. Exposed so a routing decision can be audited."""
        lowered = text.lower()
        return {
            label: sum(1 for pattern in patterns if pattern.search(lowered))
            for label, patterns in _PATTERNS
        }

    def predict(self, examples: Sequence[Example]) -> Sequence[str]:
        predictions = []
        for example in examples:
            scores = self.explain(example.text)
            best = max(scores.values())
            if best == 0:
                predictions.append(FALLBACK_LABEL)
                continue
            # dict preserves insertion order, so the first match is the
            # highest-priority queue among ties.
            predictions.append(next(label for label, hits in scores.items() if hits == best))
        return predictions

    def metadata(self) -> MethodMetadata:
        return MethodMetadata(
            method_id="ticket-rules",
            name="Keyword + Priority Rules",
            short_name="Rules",
            method_class="rules",
            complexity_rank=1,
            implementation_version=IMPLEMENTATION_VERSION,
            deterministic=True,
            auditable=True,
            cost_model=CPU_COST_MODEL,
            notes=(
                "Scores each queue by keyword hits; ties resolve by triage priority. "
                "Every routing decision is explainable from the matched terms."
            ),
        )


# One shared compute-rate assumption so the two local methods are costed on the
# same basis. Any figure derived from it is ESTIMATED, never MEASURED.
CPU_COST_MODEL = CostModel(
    basis="single vCPU-second of general-purpose cloud compute, billed by the second",
    rate_usd=0.0416,
    rate_unit="USD per vCPU-hour",
    source=(
        "AWS EC2 on-demand c7g.large us-east-1 list price, halved to one vCPU "
        "($0.0723/hr for 2 vCPU); recorded as an assumption, not a negotiated rate"
    ),
    as_of="2026-08-30",
)
