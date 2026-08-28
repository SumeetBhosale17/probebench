from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import (
    EvaluationResult,
    Evaluator,
    validate_score,
)


class LexicalEvaluator(Evaluator):
    """Checks whether the expected answer occurs in the response.

    This remains binary because the benchmark is testing exact
    retrieval of a secret/code.
    """

    name = "lexical_exact_match"

    def evaluate(self, case: BenchmarkCase, predicted: str) -> EvaluationResult:

        expected = case.expected.strip().casefold()
        response = predicted.strip().casefold()

        score = 1.0 if expected in response else 0.0

        return EvaluationResult(
            name=self.name,
            score=validate_score(score),
        )
