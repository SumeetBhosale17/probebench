from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import (
    EvaluationResult,
    Evaluator,
    validate_score,
)

RULE_VERSION = "1.0"


def _normalise(text: str) -> str:
    return " ".join(text.casefold().replace("_", " ").split()).strip(" .,!?:;")


class AnswerabilityEvaluator(Evaluator):
    """Rule-tier answerability check for negative retrieval."""

    name = "answerability_exact_match"

    def evaluate(self, case: BenchmarkCase, predicted: str) -> EvaluationResult:
        expected = _normalise(case.expected)
        response = _normalise(predicted)
        score = 1.0 if response == expected else 0.0

        return EvaluationResult(
            name=self.name,
            score=validate_score(score),
            metadata={
                "answerable": bool(case.metadata["answerable"]),
                "correct": score == 1.0,
                "rule_version": RULE_VERSION,
            },
        )
