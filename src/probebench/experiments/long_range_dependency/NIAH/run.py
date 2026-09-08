import json
import logging
from pathlib import Path
from uuid import uuid4

from probebench.benchmarks.long_range_dependency.NIAH.benchmark import NiahBenchmark
from probebench.benchmarks.long_range_dependency.NIAH.settings import NiahParams
from probebench.core.case import BenchmarkCase
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.hostinfo import collect_host_info
from probebench.core.kvprobe import probe_kv_precision
from probebench.core.model import ModelResponse
from probebench.core.preflight import build_memory_plan, format_memory_plan
from probebench.core.runner import BenchmarkRunner
from probebench.evaluation.long_range_dependency.NIAH.compliance import (
    InstructionComplianceEvaluator,
)
from probebench.evaluation.long_range_dependency.NIAH.judge import OllamaJudge
from probebench.evaluation.long_range_dependency.NIAH.lexical import LexicalEvaluator
from probebench.models.host import default_ollama_host
from probebench.models.ollama import OllamaModel
from probebench.models.registry import OllamaModelRegistry
from probebench.reporting.jsonl import JSONLWriter
from probebench.tokenizers.factory import create_tokenizer

logger = logging.getLogger(__name__)

FILLER_PATH = "data/long_range_dependency/NIAH/filler_text.txt"
NEEDLES_PATH = "data/long_range_dependency/NIAH/needles.txt"


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

    registry.ensure_availability(
        config.generation_model,
        config.resolved_judge_model() if config.judge.enabled else "",
        # NIAH stopped scoring with embeddings in D-019, but the model is
        # still ensured present: the corpus-similarity analysis embeds needles
        # and filler windows offline, and a missing model should fail at
        # startup rather than halfway through an analysis.
        config.embedding.model if config.embedding.enabled else "",
    )

    model_info = registry.inspect(config.generation_model)

    logger.info(
        "Inspected model %s (family=%s, context_length=%s, context_source=%s)",
        config.generation_model,
        model_info.family,
        model_info.context_length,
        model_info.context_length_source,
    )

    config.metadata["model_family"] = model_info.family
    config.metadata["model_parameter_size"] = model_info.parameter_size
    config.metadata["model_quantization"] = model_info.quantization
    config.metadata["supported_context_window"] = model_info.context_length
    config.metadata["supported_context_source"] = model_info.context_length_source
    config.metadata["model_capabilities"] = model_info.capabilities
    config.metadata["tokenizer_model"] = model_info.tokenizer_model
    config.metadata["tokenizer_pre"] = model_info.tokenizer_pre

    config.metadata["host"] = collect_host_info(default_ollama_host())

    host_machine = config.metadata["host"]["machine"]

    if host_machine is None:
        logger.warning(
            "Ollama host %s is not this machine: hardware provenance will be "
            "absent from every record in this run (LIMITATIONS 1.16).",
            config.metadata["host"]["ollama_host"],
        )
    else:
        logger.info(
            "Host: %s, %s logical cores, %.1f GiB RAM, GPUs: %s",
            host_machine["cpu_model"],
            host_machine["cpu_cores_logical"],
            (host_machine["ram_total_bytes"] or 0) / 1024**3,
            [gpu["name"] for gpu in host_machine["gpus"]] or "none detected",
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

    model = OllamaModel(
        model_name=config.generation_model,
        think=config.execution.think,
        keep_alive=config.execution.keep_alive,
        max_retries=config.execution.max_retries,
        retry_backoff_sec=config.execution.retry_backoff_sec,
    )

    _probe_kv_cache(config, model, model_info)

    evaluators: list[Evaluator] = [
        LexicalEvaluator(),
        # Rules before models (invariant 9). Compliance is a syntactic property
        # of a string already in hand, so it is decided offline and for free -
        # and deliberately NOT gated behind --judge or --embedding, because a
        # metric that only exists when a judge was configured could not be
        # replayed over the archive.
        InstructionComplianceEvaluator(),
    ]

    # semantic_similarity was dropped from NIAH in D-019. J-022 showed it was
    # not a weak correctness signal but a near-perfect detector of response
    # FORM (min 0.9918 bare vs max 0.7977 prose, zero overlap over 424
    # records) - the same property InstructionComplianceEvaluator now decides
    # exactly, offline, with a recorded rule version. The class is retained for
    # future families whose expected answers are prose.

    if config.judge.enabled:
        judge_model = config.resolved_judge_model()

        # Self-judging is LIMITATIONS 1.2. J-006 showed it is not a mild bias:
        # qwen3:0.6b grading its own correct answers returned 0.0 with reasons
        # that named the expected string in the clause calling it missing.
        # Warn rather than refuse - a self-judged run is a legitimate thing to
        # ask for, it is just not a reportable one.
        if judge_model == config.generation_model:
            logger.warning(
                "Judge model %s IS the generation model: this run is "
                "self-judged and its llm_judge column is not reportable "
                "(LIMITATIONS 1.2, JOURNAL J-006). Pass --judge-model to "
                "use an independent judge.",
                judge_model,
            )

        evaluators.append(
            OllamaJudge(
                model_name=judge_model,
                num_ctx=config.judge.num_ctx,
                max_predicted_chars=config.judge.max_predicted_chars,
                keep_alive=config.execution.keep_alive,
                max_retries=config.execution.max_retries,
                retry_backoff_sec=config.execution.retry_backoff_sec,
            )
        )

    max_context_tokens = config.requested_context_window or model_info.context_length

    # Validated here rather than in core/: the benchmark owns these knobs, so a
    # typo in one of them raises in the package that knows what they mean.
    params = NiahParams(**config.experiment_params)

    benchmark = NiahBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        question=params.question,
        system_prompt=params.system_prompt,
        tokenizer=tokenizer,
        target_tokens=config.sweep.target_tokens,
        depths=config.sweep.depths,
        needles_per_configuration=config.sweep.needles_per_configuration,
        context_buffer_tokens=config.sweep.context_buffer_tokens,
        max_context_tokens=max_context_tokens,
        tokenizer_provider=config.tokenizer.provider,
        tokenizer_name=config.tokenizer.name,
    )

    cases = benchmark.cases_as_generic()

    logger.info(
        "Generated %d cases for %s/%s",
        len(cases),
        config.benchmark_family,
        config.experiment,
    )

    if benchmark.skipped:
        logger.warning(
            "Skipped %d of %d planned cases (context ceiling %s). Targets dropped: %s",
            len(benchmark.skipped),
            len(cases) + len(benchmark.skipped),
            max_context_tokens,
            sorted({item["target_tokens"] for item in benchmark.skipped}),
        )

    if not cases:
        raise RuntimeError(
            f"No cases generated. Every target in {config.sweep.target_tokens} "
            f"exceeds the context ceiling of {max_context_tokens:,}. "
            "Note that --context is a CEILING that drops oversized cases; it does "
            "not shrink them. Lower --target-tokens instead."
        )

    if config.execution.sort_cases_by_num_ctx:
        # Cases sharing a num_ctx share an Ollama runner. Sorting means the
        # model reloads once per distinct context size, not once per case.
        cases.sort(key=_case_num_ctx)

    _check_memory_plan(config, model_info, cases)

    if config.execution.dry_run:
        logger.info(
            "Dry run: %d cases planned across %s, no model calls made.",
            len(cases),
            sorted({_case_num_ctx(case) for case in cases}),
        )
        return output_path

    runner = BenchmarkRunner(
        model=model,
        evaluators=evaluators,
        config=config,
    )

    writer = JSONLWriter(output_path)

    if config.execution.two_phase:
        _run_two_phase(runner, cases, writer)
    else:
        _run_single_phase(runner, cases, writer)

    _log_summary(run_id, output_path, len(cases))

    return output_path


def _probe_kv_cache(config: RunConfig, model: OllamaModel, model_info) -> None:
    """Measure the server's KV precision and refuse a run that is mislabelled.

    The flag only ever configured the memory ESTIMATOR (J-016); the server's
    actual precision lives in a daemon we usually cannot inspect, so it is
    measured rather than assumed (D-017, J-018).
    """

    if config.execution.dry_run or not config.execution.probe_kv_cache:
        return

    divisor = None

    if model_info.block_count and model_info.kv_head_count and model_info.head_dim:
        divisor = 2 * model_info.block_count * model_info.kv_head_count * model_info.head_dim

    result = probe_kv_precision(model.client, config.generation_model, divisor)

    config.metadata["kv_probe"] = result.to_metadata()

    requested = config.execution.kv_cache_type

    if not result.measured:
        logger.warning(
            "KV cache precision could not be measured (%s). Records will say "
            "'%s' was REQUESTED and make no claim about what ran.",
            result.reason,
            requested,
        )
        return

    logger.info(
        "KV cache precision measured: %.3f bytes/element -> %s (requested %s)",
        result.bytes_per_element,
        result.kv_type or "unrecognised",
        requested,
    )

    if result.kv_type is not None and result.kv_type != requested:
        # Refusing beats archiving a mislabelled record. The server is the
        # ground truth; the flag is a claim about the server.
        raise RuntimeError(
            f"KV cache precision mismatch: --kv-cache-type says {requested!r} but the "
            f"server is running {result.kv_type!r} "
            f"({result.bytes_per_element:.3f} bytes/element). "
            "ProbeBench cannot change a running daemon's KV precision - set "
            "OLLAMA_KV_CACHE_TYPE (and OLLAMA_FLASH_ATTENTION=1) on the OLLAMA "
            "SERVICE and restart it, or drop the flag."
        )


def _case_num_ctx(case: BenchmarkCase) -> int:
    """The context this case asks Ollama for."""

    return case.metadata.get("model_options", {}).get("num_ctx", 0)


def _check_memory_plan(
    config: RunConfig,
    model_info,
    cases: list[BenchmarkCase],
) -> None:
    """Refuse contexts this machine cannot hold, before loading anything."""

    if not (config.execution.enforce_memory_preflight or config.execution.dry_run):
        return

    rows = build_memory_plan(
        model_info,
        [_case_num_ctx(case) for case in cases],
        headroom_fraction=config.execution.memory_headroom_fraction,
        bytes_per_element=config.execution.kv_cache_bytes_per_element,
    )

    if not rows:
        logger.info("Memory plan: KV geometry unknown for this model, preflight skipped.")
        return

    logger.info("Memory plan:\n%s", format_memory_plan(rows))

    too_large = [row for row in rows if not row.fits]

    if too_large and config.execution.enforce_memory_preflight:
        largest = ", ".join(f"{row.num_ctx:,}" for row in too_large)

        raise RuntimeError(
            f"Insufficient memory for context size(s): {largest}.\n"
            + format_memory_plan(rows)
            + "\n\nOptions:\n"
            "  - lower --target-tokens\n"
            "  - set OLLAMA_FLASH_ATTENTION=1 and OLLAMA_KV_CACHE_TYPE=q8_0, "
            "then pass --kv-cache-type q8_0 (halves KV cost)\n"
            "  - use a smaller model\n"
            "  - override with --skip-memory-check (the run will likely fail)"
        )


def _run_two_phase(
    runner: BenchmarkRunner,
    cases: list[BenchmarkCase],
    writer: JSONLWriter,
) -> None:
    """Generate every response first, then evaluate every response.

    Single-phase alternation forces Ollama to swap between the generation
    model and the judge model on every case. On a small GPU that is several
    GB of reloading per case; two phases pay it twice for the whole run.
    """

    generated: list[tuple[BenchmarkCase, ModelResponse, str | None]] = []

    for index, case in enumerate(cases, start=1):
        response, error = runner.generate(case)

        generated.append((case, response, error))

        logger.info(
            "[gen %d/%d] case=%s num_ctx=%s latency=%.2fs%s",
            index,
            len(cases),
            case.case_id,
            _case_num_ctx(case),
            response.latency_sec,
            f" ERROR: {error}" if error else "",
        )

    for index, (case, response, error) in enumerate(generated, start=1):
        result = runner.evaluate(case, response, error)

        writer.write(result)

        logger.info(
            "[eval %d/%d] case=%s status=%s metrics=%s",
            index,
            len(cases),
            case.case_id,
            result.status,
            result.metrics,
        )


def _run_single_phase(
    runner: BenchmarkRunner,
    cases: list[BenchmarkCase],
    writer: JSONLWriter,
) -> None:
    """Generate and evaluate each case before moving to the next."""

    for index, case in enumerate(cases, start=1):
        result = runner.run_case(case)

        writer.write(result)

        logger.info(
            "[%d/%d] case=%s status=%s latency=%.2fs metrics=%s",
            index,
            len(cases),
            case.case_id,
            result.status,
            result.latency_sec,
            result.metrics,
        )


def _log_summary(
    run_id: str,
    output_path: Path,
    expected_cases: int,
) -> None:
    """Report per-status counts so partial failures are visible immediately."""

    statuses: dict[str, int] = {}

    try:
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            record = json.loads(line)
            status = record.get("response", {}).get("status", "ok")
            statuses[status] = statuses.get(status, 0) + 1

    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not summarize %s: %s", output_path, exc)
        return

    summary = ", ".join(f"{count} {name}" for name, count in sorted(statuses.items()))

    logger.info(
        "Run %s complete: %s. Wrote %d results to %s",
        run_id,
        summary or "no results",
        sum(statuses.values()),
        output_path,
    )

    if statuses.get("ok", 0) != expected_cases:
        logger.warning(
            "Run %s did not complete cleanly - inspect the 'status' field in %s",
            run_id,
            output_path,
        )
