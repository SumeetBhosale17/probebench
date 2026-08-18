from pathlib import Path
from typing import Any

import pandas as pd

from probebench.core.result import BenchmarkResult

def result_to_dataframe(
        results: list[BenchmarkResult],
) -> pd.DataFrame:

    rows: list[dict[str, Any]] = [
        result.to_dict()
        for result in results
    ]

    return pd.DataFrame(rows)

def write_results_csv(
        results: list[BenchmarkResult],
        path: str | Path,
) -> None:

    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe = result_to_dataframe(results)
    dataframe.to_csv(
        path,
        index=False,
    )
