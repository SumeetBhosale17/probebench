from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from probebench.core.case import BenchmarkCase


@dataclass
class EvaluationResult:
    """Result produced by one evaluator."""

    name: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class Evaluator(ABC):
    """Interface implemented by all Probebench Evaluators."""

    name: str

    @abstractmethod
    def evaluate(
        self,
        case: BenchmarkCase,
        predicted: str,
    ) -> EvaluationResult:
        """Evaluate a model response."""
        raise NotImplementedError


def validate_score(
    score: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """Ensure an evaluator's score falls within its allowed range."""

    if not minimum <= score <= maximum:
        raise ValueError(f"Evaluation score must be in [{minimum}, {maximum}], got {score}.")
    return float(score)
