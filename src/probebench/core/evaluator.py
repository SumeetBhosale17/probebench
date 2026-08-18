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

def validate_score(score: float) -> float:
    """Ensure every evaluator returns a score in [0, 1]."""

    if not 0.0 <= score <= 1.0:
        raise ValueError(
            f"Evaluation score must be in [0, 1], got {score}."
        )
    return float(score)