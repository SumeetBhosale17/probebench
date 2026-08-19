import json
from pathlib import Path
from typing import Any


def load_jsonl(
    path: str | Path,
) -> list[dict[str, Any]]:

    path = Path(path)

    records: list[dict[str, Any]] = []

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc

    return records
