from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkResult:
    """Complete result for one benchmark case."""

    run_id: str

    benchmark: str
    experiment: str
    case_id: str

    model: str

    expected: str
    predicted: str

    latency_sec: float

    metrics: dict[str, float] = field(default_factory=dict)

    evaluation_metadata: dict[str, Any] = field(default_factory=dict)
    case_metadata: dict[str, Any] = field(default_factory=dict)
    run_metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Convert result to a JSON-serializable record."""

        return {
            "schema_version": "1.0",
            "run": {
                "run_id": self.run_id,
                "benchmark": self.benchmark,
                "experiment": self.experiment,
                **self.run_metadata,
            },
            "case": {
                "case_id": self.case_id,
                **self.case_metadata,
            },
            "model": self.model,
            "response": {
                "expected": self.expected,
                "predicted": self.predicted,
                "latency_sec": self.latency_sec,
            },
            "metrics": self.metrics,
            "evaluation": self.evaluation_metadata,
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
                "model": self.model,
                "expected": self.expected,
                "predicted": self.predicted,
                "latency_sec": self.latency_sec,
            }
        )

        return row
