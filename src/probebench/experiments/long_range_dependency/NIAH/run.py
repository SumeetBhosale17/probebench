import logging
from pathlib import Path
from uuid import uuid4

from probebench.benchmarks.long_range_dependency.NIAH.benchmark import NiahBenchmark
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.result import BenchmarkResult
from probebench.core.runner import BenchmarkRunner
from probebench.evaluation.long_range_dependency.NIAH.judge import OllamaJudge
from probebench.evaluation.long_range_dependency.NIAH.lexical import LexicalEvaluator
from probebench.evaluation.long_range_dependency.NIAH.semantic import EmbeddingSemanticEvaluator
from probebench.models.embedding_factory import create_embedding_provider
from probebench.models.ollama import OllamaModel
from probebench.models.registry import OllamaModelRegistry
from probebench.reporting.jsonl import JSONLWriter
from probebench.tokenizers.factory import create_tokenizer

logger = logging.getLogger(__name__)


def run_niah(config: RunConfig) -> Path:

    run_id = config.run_id or uuid4().hex[:12]

    config.run_id = run_id

    output_path = (
        Path(config.output_dir)
        / "raw"
        / (
            f"{config.benchmark_family}_"
            f"{config.experiment}_"
            f"{config.generation_model.replace(':', '_')}_"
            f"{run_id}.jsonl"
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = output_path.with_suffix(".log")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    try:
        return _run_niah(config, run_id, output_path)
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()


def _run_niah(
    config: RunConfig,
    run_id: str,
    output_path: Path,
) -> Path:

    logger.info("Starting run %s for model %s", run_id, config.generation_model)

    registry = OllamaModelRegistry()

    model_info = registry.inspect(config.generation_model)

    logger.info(
        "Inspected model %s (family=%s, context_length=%s, context_source=%s)",
        config.generation_model,
        model_info.family,
        model_info.context_length,
        model_info.context_length_source,
    )

    if (
        config.requested_context_window is not None
        and model_info.context_length is not None
        and config.requested_context_window > model_info.context_length
    ):
        raise ValueError(
            "Requested context window "
            f"{config.requested_context_window:,} "
            "exceeds model-supported context "
            f"{model_info.context_length:,}."
        )

    tokenizer = create_tokenizer(config.tokenizer)
    embedding_provider = create_embedding_provider(config.embedding)

    model = OllamaModel(model_name=config.generation_model)

    evaluators: list[Evaluator] = [
        LexicalEvaluator(),
    ]

    if config.embedding.enabled and embedding_provider is not None:
        evaluators.append(EmbeddingSemanticEvaluator(embedding_provider.embed))

    if config.judge.enabled:
        evaluators.append(OllamaJudge(model_name=config.resolved_judge_model()))

    max_context_tokens = config.requested_context_window or model_info.context_length

    benchmark = NiahBenchmark(
        filler_path="data/long_range_dependency/NIAH/filler_text.txt",
        needles_path="data/long_range_dependency/NIAH/needles.txt",
        tokenizer=tokenizer,
        target_tokens=[
            4_000,
        ],
        depths=[0.0, 0.25, 0.5, 0.75, 1.0],
        needles_per_configuration=2,
        context_buffer_tokens=512,
        max_context_tokens=max_context_tokens,
    )

    cases = benchmark.cases_as_generic()

    logger.info(
        "Generated %d cases for %s/%s",
        len(cases),
        config.benchmark_family,
        config.experiment,
    )

    runner = BenchmarkRunner(
        model=model,
        evaluators=evaluators,
        config=config,
    )

    writer = JSONLWriter(output_path)

    for index, case in enumerate(cases, start=1):
        result: BenchmarkResult = runner.run_case(case)

        result.run_metadata["model_family"] = model_info.family
        result.run_metadata["model_parameter_size"] = model_info.parameter_size
        result.run_metadata["model_quantization"] = model_info.quantization
        result.run_metadata["supported_context_window"] = model_info.context_length
        result.run_metadata["supported_context_source"] = model_info.context_length_source
        result.run_metadata["model_capabilities"] = model_info.capabilities
        result.run_metadata["tokenizer_model_metadata"] = model_info.tokenizer_model
        result.run_metadata["tokenizer_pre_metadata"] = model_info.tokenizer_pre

        writer.write(result)

        logger.info(
            "[%d/%d] case=%s latency=%.2fs metrics=%s",
            index,
            len(cases),
            case.case_id,
            result.latency_sec,
            result.metrics,
        )

    logger.info("Run %s complete. Wrote %d results to %s", run_id, len(cases), output_path)

    return output_path
