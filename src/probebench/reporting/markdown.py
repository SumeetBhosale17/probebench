from pathlib import Path
from typing import cast

import pandas as pd


def _to_markdown(
    dataframe: pd.DataFrame,
) -> str:
    """Convert a DataFrame to Markdown."""
    return dataframe.to_markdown()


def write_long_range_summary(
    dataframe: pd.DataFrame,
    path: str | Path,
) -> None:
    """Write a Markdown summary of long-range dependency results."""

    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    metric_columns = [
        column
        for column in [
            "lexical",
            "semantic_similarity",
            "llm_judge",
        ]
        if column in dataframe.columns
    ]

    lines = [
        "# Long-Range Dependency Summary",
        "",
    ]

    if dataframe.empty:
        lines.append("No benchmark results were generated.")
        path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )
        return

    overall_metrics = dataframe[metric_columns].mean().to_frame("mean_score")

    lines.extend(
        [
            "## Overall Metrics",
            "",
            _to_markdown(overall_metrics),
            "",
        ]
    )

    if "context_tokens" in dataframe.columns:
        context_metrics = cast(
            pd.DataFrame,
            dataframe.groupby("context_tokens")[metric_columns].mean(),
        )

        lines.extend(
            [
                "## Metrics by Context Length",
                "",
                _to_markdown(context_metrics),
                "",
            ]
        )

    if "depth" in dataframe.columns:
        depth_metrics = cast(
            pd.DataFrame,
            dataframe.groupby("depth")[metric_columns].mean(),
        )

        lines.extend(
            [
                "## Metrics by Needle Depth",
                "",
                _to_markdown(depth_metrics),
                "",
            ]
        )

    if {
        "context_tokens",
        "depth",
    }.issubset(dataframe.columns):
        lines.extend(
            [
                "## Context Length × Depth",
                "",
            ]
        )

        for metric in metric_columns:
            pivot = dataframe.pivot_table(
                index="context_tokens",
                columns="depth",
                values=metric,
                aggfunc="mean",
            )

            lines.extend(
                [
                    f"### {metric}",
                    "",
                    _to_markdown(pivot),
                    "",
                ]
            )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
