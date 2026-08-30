"""TF-IDF + logistic regression — the traditional ML baseline.

The honest representative of its class for short-text classification: cheap to
fit, fast to serve, and its coefficients can be read, which is why it is marked
auditable where a neural method would not be.

Feature choice is not assumed. ``select_analyzer`` runs a comparison on a
validation split carved out of the *training* data only, so the evaluation
split is never consulted while choosing; each problem records the winner and
its margin in its dataset card.
"""

from __future__ import annotations

from collections.abc import Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.benchmarks.base import Example, MethodConfig, MethodMetadata
from app.benchmarks.methods.keyword_rules import CPU_COST_MODEL

IMPLEMENTATION_VERSION = "3.0.0"

ANALYZERS: dict[str, dict[str, object]] = {
    "word": {"analyzer": "word", "ngram_range": (1, 2)},
    "char_wb": {"analyzer": "char_wb", "ngram_range": (3, 5)},
}


def build_pipeline(analyzer: str) -> Pipeline:
    return Pipeline(
        [
            (
                "features",
                TfidfVectorizer(
                    min_df=2,
                    sublinear_tf=True,
                    lowercase=True,
                    **ANALYZERS[analyzer],
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=3000,
                    C=1.0,
                    class_weight="balanced",
                    # lbfgs is deterministic given fixed inputs, so a rerun on
                    # the same data reproduces the same model.
                    solver="lbfgs",
                ),
            ),
        ]
    )


class TfidfLogisticRegressionMethod:
    """Word or character n-grams into a linear classifier."""

    def __init__(self, analyzer: str = "word", notes: str = "") -> None:
        if analyzer not in ANALYZERS:
            raise ValueError(f"Unknown analyzer {analyzer!r}")
        self._analyzer = analyzer
        self._notes = notes
        self._pipeline: Pipeline | None = None

    def setup(self, config: MethodConfig) -> None:
        if not config.training_examples:
            raise ValueError("TF-IDF + logistic regression requires training examples")
        self._pipeline = build_pipeline(self._analyzer)
        self._pipeline.fit(
            [e.text for e in config.training_examples],
            [e.label for e in config.training_examples],
        )

    def predict(self, examples: Sequence[Example]) -> Sequence[str]:
        if self._pipeline is None:
            raise RuntimeError("setup() must run before predict()")
        return list(self._pipeline.predict([e.text for e in examples]))

    def metadata(self) -> MethodMetadata:
        return MethodMetadata(
            method_id="ml",
            name="TF-IDF + Logistic Regression",
            short_name="Traditional ML",
            method_class="traditional-ml",
            complexity_rank=2,
            implementation_version=IMPLEMENTATION_VERSION,
            deterministic=True,
            auditable=True,
            cost_model=CPU_COST_MODEL,
            model_name=f"tfidf-{self._analyzer}-logreg",
            notes=self._notes,
        )
