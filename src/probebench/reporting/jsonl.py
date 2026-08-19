import json
from pathlib import Path

from probebench.core.result import BenchmarkResult


class JSONLWriter:
    """Write benchmark results are JSON Lines."""

    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def write(self, result: BenchmarkResult) -> None:
        record = result.to_record()

        with self.path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )

            file.write("\n")
