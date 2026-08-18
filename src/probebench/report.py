import logging
from pathlib import Path

from probebench.benchmarks.long_range_dependency.NIAH.benchmark import (
    NiahBenchmark,
)
from probebench.core.runner import BenchmarkRunner
from probebench.evaluation.long_range_dependency.NIAH.lexical import (
    LexicalEvaluator,
)
from probebench.evaluation.long_range_dependency.NIAH.semantic import (
    EmbeddingSemanticEvaluator,
)
from probebench.models.ollama import OllamaModel
from probebench.reporting.csv import (
    result_to_dataframe,
    write_results_csv,
)
from probebench.reporting.markdown import (
    write_long_range_summary,
)

logger = logging.getLogger(__name__)


def run_long_range_dependency(
    model_name: str = "llama3.1:8b",
    judge_model_name: str | None = None,
    embedding_model_name: str = "nomic-embed-text",
) -> None:

    logger.info(
        "Starting Needle-in-a-haystack benchmark with model=%s",
        model_name,
    )

    model = OllamaModel(
        model_name=model_name,
    )

    judge = OllamaModel(
        model_name=judge_model_name if judge_model_name else model_name,
    )

    semantic_evaluator = EmbeddingSemanticEvaluator(
        embedder=lambda text: model.embed(
            model=embedding_model_name,
            text=text,
        )
    )

    evaluators = [
        LexicalEvaluator(),
        semantic_evaluator,
        judge,
    ]

    benchmark = NiahBenchmark(
        filler_path=("data/long_range_dependency/NIAH/filler_text.txt"),
        needles_path=("data/long_range_dependency/NIAH/needles.txt"),
        target_tokens=[
            4_000,
            8_000,
            16_000,
            32_000,
        ],
        depths=[
            0.00,
            0.25,
            0.50,
            0.75,
            1.00,
        ],
        needles_per_configuration=5,
        context_buffer_tokens=512,
        max_context_tokens=32_768,
    )

    cases = benchmark.cases_as_generic()

    logger.info(
        "Generated %d benchmark cases.",
        len(cases),
    )

    runner = BenchmarkRunner(
        model=model,
        evaluators=evaluators,
    )

    results = []

    for index, case in enumerate(cases, start=1):
        logger.info(
            "[%d/%d] Running %s",
            index,
            len(cases),
            case.case_id,
        )

        result = runner.run_case(case)

        results.append(result)

        logger.info(
            "[%s] lexical=%.3f semantic=%.3f judge=%.3f latency=%.2f",
            case.case_id,
            result.metrics["lexical"],
            result.metrics["semantic_similarity"],
            result.metrics["llm_judge"],
            result.latency_sec,
        )

    output_csv = Path("results/raw/long_range_dependency/NIAH/benchmarking_raw.csv")
    output_md = Path("results/reports/long_range_dependency/NIAH/summary_report.md")

    write_results_csv(
        results,
        output_csv,
    )

    dataframe = result_to_dataframe(results)
    write_long_range_summary(
        dataframe,
        output_md,
    )

    logger.info("Raw results written to %s", output_csv)
    logger.info(
        "Summary written to %s",
        output_md,
    )

    print("\nEvaluation summary:")
    print(
        dataframe[
            [
                "lexical",
                "semantic_similarity",
                "llm_judge",
            ]
        ].mean()
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s - %(levelname)s - %(message)s"),
    )

    run_long_range_dependency()


if __name__ == "__main__":
    main()
