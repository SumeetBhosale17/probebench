from dataclasses import dataclass, field
from typing import Any

@dataclass
class BenchmarkResult:
    """Complete result for one benchmark case."""

    benchmark: str
    case_id: str
    model: str

    expected: str
    predicted: str

    latency_sec: float

    metrics: dict[str, float] = field(default_factory=dict)

    metadata: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Flatten the result for CSV/reporting."""

        result: dict[str, Any] = {
            "benchmark": self.benchmark,
            "case_id": self.case_id,
            "model": self.model,
            "expected": self.expected,
            "predicted": self.predicted,
            "latency_sec": self.latency_sec,
        }
        result.update(self.metrics)
        result.update(self.metadata)
        return result