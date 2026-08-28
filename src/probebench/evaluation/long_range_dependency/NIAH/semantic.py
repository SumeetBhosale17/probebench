import math
from collections.abc import Callable

from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import (
    EvaluationResult,
    Evaluator,
    validate_score,
)


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:

    if len(vector_a) != len(vector_b):
        raise ValueError("Embedding dimensions do not match.")

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=True))

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0.0 or norm_b == 0.0:
        raise ValueError("Cannot calculate cosine similarity for a zero vector.")

    # Clamp away floating-point overshoot past the true [-1, 1] range.
    return max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))


class EmbeddingSemanticEvaluator(Evaluator):
    """
    Measures semantic similarity between expected and predicted text.

    Note:
    This is similarity metric, not a correctness metric.
    """

    name = "semantic_similarity"

    def __init__(
        self,
        embedder: Callable[[str], list[float]],
        batch_embedder: Callable[[list[str]], list[list[float]]] | None = None,
    ) -> None:
        self.embedder = embedder

        # When the provider supports it, expected and predicted go over the
        # wire together, halving the embed requests per case.
        self.batch_embedder = batch_embedder

    def evaluate(self, case: BenchmarkCase, predicted: str) -> EvaluationResult:

        if self.batch_embedder is not None:
            expected_embedding, predicted_embedding = self.batch_embedder(
                [case.expected, predicted]
            )
        else:
            expected_embedding = self.embedder(case.expected)
            predicted_embedding = self.embedder(predicted)

        score = cosine_similarity(
            expected_embedding,
            predicted_embedding,
        )

        return EvaluationResult(
            name=self.name,
            score=validate_score(score, minimum=-1.0, maximum=1.0),
        )
