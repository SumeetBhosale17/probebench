from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkCase:
    """Generic test case shared by all ProbeBench benchmarks"""

    case_id: str
    benchmark: str
    prompt: str
    expected: str
    metadata: dict[str, Any] = field(default_factory=dict)
