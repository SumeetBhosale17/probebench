"""The generic experiment pipeline: everything that is not family-specific.

Extracted from `long_range_dependency/NIAH/run.py` (D-021), which was the only
runner until the keyed families arrived. It is deliberately NOT under a family
directory - a shared pipeline living inside `long_range_dependency/` would be
the same scope violation as putting needles in `core/`, one level down.

The ordering in here is knowledge, not arrangement, and most of it was paid for:

  settings -> host -> KV probe -> cases -> memory plan -> generate -> evaluate

* The KV probe runs BEFORE case generation so it cannot evict the sweep's
  runner (invariant 3, R-002).
* The memory plan runs before any model call (invariant 2) - a context the host
  cannot hold killed the Ollama runner and took whole runs with it.
* Generation and evaluation are two phases by default, because interleaving a
  judge swaps models on every case (R-002).

Three copies of that ordering would be two chances to regress it silently, which
is the argument D-021 actually turned on.

An experiment supplies an `ExperimentPlug`: how to build its cases, and how to
score them. Everything else is here.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from probebench.core.case import BenchmarkCase
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.hostinfo import collect_host_info
from probebench.core.kvprobe import probe_kv_precision
from probebench.core.model import ModelResponse
from probebench.core.preflight import build_memory_plan, format_memory_plan
from probebench.core.runner import BenchmarkRunner
from probebench.core.tokenizer import Tokenizer
from probebench.models.host import default_ollama_host
from probebench.models.ollama import OllamaModel
from probebench.models.registry import OllamaModelRegistry
from probebench.reporting.jsonl import JSONLWriter
from probebench.tokenizers.factory import create_tokenizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaseBundle:
    """What a family's case builder hands back.

    `skipped` is carried alongside the cases rather than logged inside the
    builder, because invariant 4 requires skipped cases to be REPORTED and the
    pipeline is what owns reporting. A builder that logged and dropped would
    satisfy the letter of that and lose the count.
    """

    cases: list[BenchmarkCase]
    skipped: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ExperimentPlug:
    """The three things that differ between experiments.

    Counted from the NIAH runner, this is genuinely all of it: the other ~430
    lines were generic and are now above.
    """

    # (config, tokenizer, max_context_tokens) -> CaseBundle
    build_cases: Callable[[RunConfig, Tokenizer, int | None], CaseBundle]

    # (config) -> evaluators, in the order they should run. Rules first
    # (invariant 9) is the family's responsibility because only the family
    # knows which of its evaluators are rules.
    build_evaluators: Callable[[RunConfig], list[Evaluator]]

    # Whether an embedding model must be present. NIAH stopped scoring with
    # embeddings (D-019) but still ensures the model exists, so the offline
    # corpus-similarity analysis fails at startup rather than halfway through.
    needs_embedding_model: bool = True


def run_experiment(config: RunConfig, plug: ExperimentPlug) -> Path:
    """Run one experiment end to end and return the path it wrote."""

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

    # Attached to the PACKAGE logger, not this module's. Before D-021 the
    # handler sat on the NIAH runner's own logger, so the log captured only
    # that one module - and after the extraction a family's own messages (the
    # self-judging warning that LIMITATIONS 1.2 depends on being visible) would
    # have gone to a sibling logger and been dropped silently. Widening to
    # `probebench` also picks up the runner, the model client and the memory
    # preflight, which is what a run log was always meant to contain.
    package_logger = logging.getLogger("probebench")
    package_logger.addHandler(file_handler)

    previous_level = package_logger.level

    if previous_level > logging.INFO or previous_level == logging.NOTSET:
        package_logger.setLevel(logging.INFO)

    try:
        return _execute(config, run_id, output_path, plug)
    finally:
        package_logger.removeHandler(file_handler)
        package_logger.setLevel(previous_level)
        file_handler.close()


def _execute(
    config: RunConfig,
    run_id: str,
    output_path: Path,
    plug: ExperimentPlug,
) -> Path:

    logger.info("Starting run %s for model %s", run_id, config.generation_model)

    registry = OllamaModelRegistry()

    registry.ensure_availability(
        config.generation_model,
        config.resolved_judge_model() if config.judge.enabled else "",
        config.embedding.model if (config.embedding.enabled and plug.needs_embedding_model) else "",
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

    evaluators = plug.build_evaluators(config)

    max_context_tokens = config.requested_context_window or model_info.context_length

    bundle = plug.build_cases(config, tokenizer, max_context_tokens)

    cases = bundle.cases

    logger.info(
        "Generated %d cases for %s/%s",
        len(cases),
        config.benchmark_family,
        config.experiment,
    )

    if bundle.skipped:
        logger.warning(
            "Skipped %d of %d planned cases (context ceiling %s). Targets dropped: %s",
            len(bundle.skipped),
            len(cases) + len(bundle.skipped),
            max_context_tokens,
            sorted({item["target_tokens"] for item in bundle.skipped}),
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

    result = probe_kv_precision(
        model.client,
        config.generation_model,
        divisor,
        # Ollama clamps num_ctx to the model's window and /api/ps reports the
        # clamped value, so the probe must know the ceiling or it matches
        # nothing (J-028).
        max_context=model_info.context_length,
    )

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
