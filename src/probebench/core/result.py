from dataclasses import dataclass, field
from typing import Any

from probebench.core.schema import CURRENT_SCHEMA_VERSION


@dataclass
class BenchmarkResult:
    """Complete result for one benchmark case."""

    run_id: str

    benchmark: str
    experiment: str
    case_id: str

    # Model identity
    model_name: str
    model_provider: str

    # Response
    expected: str
    predicted: str
    latency_sec: float

    # Scalar evaluation metrics
    metrics: dict[str, float] = field(default_factory=dict)

    # Evaluator-specific diagnostics and metadata
    evaluation_details: dict[str, Any] = field(default_factory=dict)

    # Benchmark-specific case metadata
    case_metadata: dict[str, Any] = field(default_factory=dict)

    # Model metadata
    model_metadata: dict[str, Any] = field(default_factory=dict)

    # Generation configuration
    generation_metadata: dict[str, Any] = field(default_factory=dict)

    # Tokenization configuration
    tokenization_metadata: dict[str, Any] = field(default_factory=dict)

    # Evaluation configuration
    evaluation_metadata: dict[str, Any] = field(default_factory=dict)

    status: str = "ok"  # ok | generation_error | evaluation_error
    error: str | None = None

    def to_record(self) -> dict[str, Any]:
        """Convert result to a JSON-serializable record."""

        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "run": {
                "run_id": self.run_id,
                "benchmark": self.benchmark,
                "experiment": self.experiment,
            },
            "model": {
                "name": self.model_name,
                "provider": self.model_provider,
                **self.model_metadata,
            },
            "generation": self.generation_metadata,
            "tokenization": self.tokenization_metadata,
            "evaluation": self.evaluation_metadata,
            "case": {
                "case_id": self.case_id,
                **self.case_metadata,
            },
            "response": {
                "expected": self.expected,
                "predicted": self.predicted,
                "latency_sec": self.latency_sec,
                "status": self.status,
                "error": self.error,
            },
            "metrics": self.metrics,
            "evaluation_details": self.evaluation_details,
        }

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten this result into a single row for tabular reporting."""

        row: dict[str, Any] = dict(self.case_metadata)
        row.update(self.metrics)

        row.update(
            {
                "run_id": self.run_id,
                "benchmark": self.benchmark,
                "experiment": self.experiment,
                "case_id": self.case_id,
                "model_name": self.model_name,
                "model_provider": self.model_provider,
                "expected": self.expected,
                "predicted": self.predicted,
                "latency_sec": self.latency_sec,
                "status": self.status,
            }
        )

        return row
