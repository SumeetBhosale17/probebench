import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from probebench.core.config import (
    EmbeddingConfig,
    ExecutionConfig,
    JudgeConfig,
    RunConfig,
    SweepConfig,
    TokenizerConfig,
)
from probebench.core.health import run_health_checks
from probebench.core.preflight import (
    build_memory_plan,
    format_memory_plan,
    max_feasible_num_ctx,
    recommend_target_tokens,
)
from probebench.core.settings import ConfigError, ResolvedSettings, load_settings
from probebench.experiments.registry import (
    ExperimentSpec,
    all_experiments,
    get_experiment,
    required_data_files,
    resolve_experiments,
)
from probebench.models.installer import install_missing_models
from probebench.models.registry import OllamaModelRegistry

logger = logging.getLogger(__name__)

# Commands the argv pre-processor recognizes. Anything else in first
# position is treated as a model name, so `probebench qwen3:4b` works.
KNOWN_COMMANDS = {
    "all",
    "doctor",
    "experiments",
    "models",
    "plan",
    "run",
}

PROFILES: dict[str, list[int]] = {
    "quick": [4_000, 8_000],
    "standard": [4_000, 8_000, 16_000, 32_000],
    "full": [4_000, 8_000, 16_000, 32_000, 64_000, 128_000],
}

METRIC_COLUMNS = (
    # The two axes NIAH scores since D-018: did it retrieve, and did it obey.
    # Printed side by side because reporting either alone hides half the task -
    # llama3:8b retrieves 74% and complies 0%, and a single number would be
    # dominated by whichever is lower without saying which.
    "lexical_exact_match",
    "instruction_compliance",
    # Retained so archived runs still render; dropped from NIAH in D-019.
    "semantic_similarity",
    "llm_judge",
)


# =====================================================
# argument parsing
# =====================================================


def _int_list(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _float_list(raw: str) -> list[float]:
    return [float(part.strip()) for part in raw.split(",") if part.strip()]


def _str_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _add_shared_run_options(parser: argparse.ArgumentParser) -> None:
    """Options common to `run` and `all`."""

    parser.add_argument(
        "--context",
        type=int,
        default=None,
        help=(
            "CEILING on model context. Cases larger than this are DROPPED, not "
            "shrunk. To change case sizes use --target-tokens."
        ),
    )

    parser.add_argument(
        "--profile",
        choices=["auto", *PROFILES],
        default=None,
        help=(
            "Context sweep preset. 'auto' sizes the sweep to this machine's "
            "free RAM and VRAM. Ignored when --target-tokens is given."
        ),
    )

    parser.add_argument(
        "--target-tokens",
        type=_int_list,
        default=None,
        help="Comma-separated haystack sizes, e.g. 4000,8000,16000. Overrides --profile.",
    )

    parser.add_argument(
        "--depths",
        type=_float_list,
        default=None,
        help="Comma-separated needle depths in [0,1].",
    )

    parser.add_argument(
        "--needles",
        type=int,
        default=None,
        help="Needles per (length, depth) configuration.",
    )

    parser.add_argument(
        "--tokenizer",
        default=None,
        help="Tokenizer encoding.",
    )

    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model.",
    )

    parser.add_argument(
        "--judge-model",
        default=None,
        help="LLM judge model. Defaults to the generation model.",
    )

    parser.add_argument(
        "--judge-context",
        type=int,
        default=None,
        help="Pinned judge context. Keeping this fixed avoids per-case model reloads.",
    )

    parser.add_argument(
        "--kv-cache-type",
        choices=["f16", "q8_0"],
        default=None,
        help=(
            "KV cache precision assumed when estimating memory. Set OLLAMA_KV_CACHE_TYPE to match."
        ),
    )

    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--no-embedding", action="store_true")

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Abort the run on the first case failure.",
    )

    parser.add_argument(
        "--single-phase",
        action="store_true",
        help="Judge each case immediately (causes model reloads).",
    )

    parser.add_argument(
        "--skip-memory-check",
        action="store_true",
        help="Run even when the memory plan says a context will not fit.",
    )

    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip the pre-run environment checks.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build cases and print the memory plan without calling any model.",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Install missing Ollama models without prompting.",
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for raw results.",
    )

    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Path to a probebench.toml. Defaults to the nearest one at or above "
            "the working directory, or $PROBEBENCH_CONFIG."
        ),
    )

    parser.add_argument(
        "--machine",
        default=None,
        help=(
            "Name of a [machine.*] section. Machine sections may only carry "
            "execution settings, never anything that changes what is measured. "
            "Defaults to $PROBEBENCH_MACHINE."
        ),
    )

    parser.add_argument(
        "--experiment-profile",
        default=None,
        help="Name of an [experiment.*] section, layered over [defaults].",
    )


def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="probebench",
        description=(
            "ProbeBench LLM benchmarking framework.\n\n"
            "Shortcut: `probebench <model>` runs every experiment against that model."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # -------------------------------------------------
    # models
    # -------------------------------------------------

    models_parser = subparsers.add_parser(
        "models",
        help="Manage local Ollama models.",
    )

    models_subparsers = models_parser.add_subparsers(
        dest="models_command",
        required=True,
    )

    models_subparsers.add_parser(
        "list",
        help="List installed Ollama models.",
    )

    inspect_parser = models_subparsers.add_parser(
        "inspect",
        help="Inspect an Ollama model.",
    )

    inspect_parser.add_argument(
        "model",
        help="Model name.",
    )

    pull_parser = models_subparsers.add_parser(
        "pull",
        help="Install a model via Ollama.",
    )

    pull_parser.add_argument("model", help="Model name.")
    pull_parser.add_argument("--yes", "-y", action="store_true")

    # -------------------------------------------------
    # experiments
    # -------------------------------------------------

    experiments_parser = subparsers.add_parser(
        "experiments",
        help="List available experiments.",
    )

    experiments_subparsers = experiments_parser.add_subparsers(
        dest="experiments_command",
        required=True,
    )

    experiments_subparsers.add_parser(
        "list",
        help="List available experiments.",
    )

    # -------------------------------------------------
    # doctor
    # -------------------------------------------------

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check that this machine can run ProbeBench.",
    )

    doctor_parser.add_argument(
        "model",
        nargs="?",
        default=None,
        help="Optional model to include in the checks.",
    )

    doctor_parser.add_argument("--judge-model", default=None)
    doctor_parser.add_argument("--embedding-model", default="nomic-embed-text")
    doctor_parser.add_argument("--tokenizer", default="cl100k_base")
    doctor_parser.add_argument("--output-dir", default="results")
    doctor_parser.add_argument("--yes", "-y", action="store_true")

    # -------------------------------------------------
    # plan
    # -------------------------------------------------

    plan_parser = subparsers.add_parser(
        "plan",
        help="Show which context sizes this machine can run for a model.",
    )

    plan_parser.add_argument("model", help="Generation model.")

    plan_parser.add_argument(
        "--target-tokens",
        type=_int_list,
        default=None,
        help="Context sizes to evaluate. Defaults to a standard ladder.",
    )

    plan_parser.add_argument("--kv-cache-type", choices=["f16", "q8_0"], default="f16")

    # -------------------------------------------------
    # all
    # -------------------------------------------------

    all_parser = subparsers.add_parser(
        "all",
        help="Run every experiment against one model.",
    )

    all_parser.add_argument("model", help="Generation model.")

    all_parser.add_argument(
        "--experiments",
        type=_str_list,
        default=None,
        help="Comma-separated subset, e.g. NIAH. Defaults to all registered experiments.",
    )

    _add_shared_run_options(all_parser)

    # -------------------------------------------------
    # run
    # -------------------------------------------------

    run_parser = subparsers.add_parser(
        "run",
        help="Run one benchmark experiment.",
    )

    run_parser.add_argument(
        "--benchmark",
        required=True,
        choices=sorted({spec.family for spec in all_experiments()}),
    )

    run_parser.add_argument(
        "--experiment",
        required=True,
        choices=sorted({spec.name for spec in all_experiments()}),
    )

    run_parser.add_argument(
        "--model",
        required=True,
        help="Generation model.",
    )

    _add_shared_run_options(run_parser)

    return parser


# =====================================================
# models / experiments
# =====================================================


def list_models() -> None:

    registry = OllamaModelRegistry()

    try:
        models = registry.list_models()

    except Exception as exc:
        print(
            f"Failed to connect to Ollama: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    if not models:
        print("No Ollama models found.")
        return

    print("Installed Ollama Models")
    print("=" * 60)

    for index, model in enumerate(
        models,
        start=1,
    ):
        print(f"{index}. {model.name}")

        if model.family:
            print(f"    Family: {model.family}")

        if model.parameter_size:
            print(f"    Parameters: {model.parameter_size}")

        if model.quantization:
            print(f"    Quantization: {model.quantization}")

        if model.size_bytes:
            print(f"    Size: {model.size_bytes / 1024**3:.1f} GiB")

        print()


def inspect_model(
    model_name: str,
) -> None:

    registry = OllamaModelRegistry()

    try:
        info = registry.inspect(model_name)

    except Exception as exc:
        print(
            f"Failed to inspect '{model_name}': {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print(f"Model:              {info.name}")

    print(f"Family:             {info.family or 'unknown'}")

    print(f"Parameters:         {info.parameter_size or 'unknown'}")

    print(f"Quantization:       {info.quantization or 'unknown'}")

    context = f"{info.context_length:,}" if info.context_length else "unknown"

    print(f"Supported context:  {context}")

    if info.context_length_source:
        print(f"Context source:     {info.context_length_source}")

    capabilities = ", ".join(info.capabilities) if info.capabilities else "unknown"

    print(f"Capabilities:       {capabilities}")

    print(f"Tokenizer model:    {info.tokenizer_model or 'unknown'}")

    print(f"Tokenizer pre:      {info.tokenizer_pre or 'unknown'}")

    if info.size_bytes:
        print(f"Weights on disk:    {info.size_bytes / 1024**3:.2f} GiB")

    print()
    print("Geometry (the inputs to the KV cache formula)")
    print(f"  Layers:           {info.block_count or 'unknown'}")
    print(f"  Attention heads:  {info.head_count or 'unknown'}")
    print(f"  KV heads:         {info.kv_head_count or 'unknown'}")

    if info.head_count and info.kv_head_count:
        # A GQA ratio above 1 is why KV cache is far smaller than a naive
        # n_heads-based estimate would suggest.
        print(f"  GQA ratio:        {info.head_count / info.kv_head_count:.0f}:1")

    print(f"  Head dim:         {info.head_dim or 'unknown'}")
    print(f"  Embedding length: {info.embedding_length or 'unknown'}")

    per_token = info.kv_bytes_per_token()

    if not per_token:
        print()
        print("KV cache per token: unknown (GGUF metadata is missing geometry)")
        return

    print()
    print("KV cache per token  (2 x layers x kv_heads x head_dim x bytes_per_element)")
    print(
        f"  f16:  2 x {info.block_count} x {info.kv_head_count} x {info.head_dim} x 2"
        f" = {per_token:,} B/token = {per_token / 1024:.0f} KiB/token"
    )

    per_token_q8 = info.kv_bytes_per_token(bytes_per_element=1)

    if per_token_q8:
        print(f"  q8_0: half that            = {per_token_q8 / 1024:.0f} KiB/token")

    print()
    print(f"  {'context':>10}  {'KV @ f16':>12}  {'KV @ q8_0':>12}")

    ladder = [4_000, 8_000, 16_000, 32_000, 64_000, 128_000]

    if info.context_length:
        ladder.append(info.context_length)

    for size in sorted(set(size for size in ladder if size <= (info.context_length or 0))):
        f16 = per_token * size
        q8 = (per_token_q8 or 0) * size

        marker = "  <- advertised max" if size == info.context_length else ""

        print(f"  {size:>10,}  {f16 / 1024**3:>10.1f} G  {q8 / 1024**3:>10.1f} G{marker}")

    print()
    print("Run `probebench plan <model>` for what THIS machine can actually hold.")


def pull_model_command(model_name: str, assume_yes: bool) -> None:

    still_missing = install_missing_models([model_name], assume_yes=assume_yes)

    if still_missing:
        print(f"'{model_name}' was not installed.", file=sys.stderr)
        raise SystemExit(1)

    print(f"'{model_name}' is installed.")


def list_experiments() -> None:

    print("Available ProbeBench Experiments")
    print("=" * 60)

    by_family: dict[str, list[ExperimentSpec]] = {}

    for spec in all_experiments():
        by_family.setdefault(spec.family, []).append(spec)

    for family, specs in by_family.items():
        print(family)

        for index, spec in enumerate(specs):
            connector = "└──" if index == len(specs) - 1 else "├──"
            print(f"    {connector} {spec.name}: {spec.description}")

    print()
    print("Run everything against one model:  probebench <model>")


# =====================================================
# doctor / plan
# =====================================================


def _health_and_install(
    *,
    required_models: list[str],
    data_files: list[str],
    tokenizer_name: str,
    output_dir: str,
    assume_yes: bool,
    quiet: bool = False,
) -> bool:
    """Run health checks, offering to install anything missing.

    Returns True when the environment is fit to run.
    """

    report = run_health_checks(
        required_models=required_models,
        data_files=data_files,
        tokenizer_name=tokenizer_name,
        output_dir=output_dir,
    )

    if not quiet or not report.ok:
        print(report.render())
        print()

        # The installer writes its prompt to the terminal directly; flush so
        # the report cannot appear after it.
        sys.stdout.flush()

    if report.ok:
        return True

    # The one failure we can fix for the user is a model that is simply
    # not pulled yet.
    if report.missing_models:
        still_missing = install_missing_models(
            report.missing_models,
            assume_yes=assume_yes,
        )

        if not still_missing:
            report = run_health_checks(
                required_models=required_models,
                data_files=data_files,
                tokenizer_name=tokenizer_name,
                output_dir=output_dir,
            )

            if report.ok:
                print()
                print("All checks pass after installation.")
                print()
                return True

            print()
            print(report.render())

    return report.ok


def doctor_command(args: argparse.Namespace) -> None:

    required: list[str] = []

    if args.model:
        required.append(args.model)
        required.append(args.judge_model or args.model)
        required.append(args.embedding_model)

    ok = _health_and_install(
        required_models=required,
        data_files=required_data_files(all_experiments()),
        tokenizer_name=args.tokenizer,
        output_dir=args.output_dir,
        assume_yes=args.yes,
    )

    if args.model and ok:
        print()
        _print_capability_report(args.model, None, "f16")

    raise SystemExit(0 if ok else 1)


def _print_capability_report(
    model_name: str,
    target_tokens: list[int] | None,
    kv_cache_type: str,
) -> list[int]:
    """Show what this machine can afford for a model. Returns feasible targets."""

    registry = OllamaModelRegistry()

    try:
        info = registry.inspect(model_name)
    except Exception as exc:
        print(f"Cannot inspect '{model_name}': {exc}", file=sys.stderr)
        return []

    bytes_per_element = 1 if kv_cache_type == "q8_0" else 2

    print(f"Capability plan for {model_name}")
    print("=" * 60)

    per_token = info.kv_bytes_per_token(bytes_per_element)

    if per_token is None:
        print("  KV geometry unavailable - cannot estimate memory for this model.")
        return []

    print(f"  Architecture:       {info.family or 'unknown'}, {info.block_count} layers")
    print(f"  Advertised context: {info.context_length:,}" if info.context_length else "")
    print(f"  KV cache per token: {per_token / 1024:.0f} KiB ({kv_cache_type})")

    ceiling = max_feasible_num_ctx(info, bytes_per_element=bytes_per_element)

    if ceiling is not None:
        print(f"  Largest context this machine can hold: {ceiling:,} tokens")

        if info.context_length and ceiling < info.context_length:
            print(
                f"  NOTE: the model supports {info.context_length:,} but this "
                "machine cannot hold that much KV cache."
            )

    print()

    ladder = target_tokens or PROFILES["full"] + [256_000]

    rows = build_memory_plan(
        info,
        [size + 512 for size in ladder],
        bytes_per_element=bytes_per_element,
    )

    print(format_memory_plan(rows))
    print()

    feasible = recommend_target_tokens(info, bytes_per_element=bytes_per_element)

    print(f"  Recommended sweep: {','.join(str(size) for size in feasible)}")

    return feasible


def plan_command(args: argparse.Namespace) -> None:

    _print_capability_report(
        args.model,
        args.target_tokens,
        args.kv_cache_type,
    )


# =====================================================
# running
# =====================================================


def _pick(*candidates: Any) -> Any:
    """First non-None candidate, in precedence order.

    None is the only "not set" marker in the whole layering, which is why the
    CLI defaults had to become None: argparse cannot otherwise distinguish "the
    user asked for the default" from "the user did not ask", so CLI would
    silently win over the file on every single run (D-016).
    """

    for candidate in candidates:
        if candidate is not None:
            return candidate

    return None


def _resolve_target_tokens(
    args: argparse.Namespace,
    settings: ResolvedSettings,
    model_name: str,
    kv_cache_type: str,
) -> list[int]:
    """Decide the context sweep: CLI list, file list, named profile, or auto."""

    if args.target_tokens:
        return args.target_tokens

    if settings.experiment.target_tokens:
        return settings.experiment.target_tokens

    profile = args.profile or "auto"

    if profile != "auto":
        return PROFILES[profile]

    if settings.fleet.forbid_auto_profile:
        # LIMITATIONS 1.6: auto sizes the sweep from THIS host's free RAM, so
        # two machines running the same command produce different sweeps. A
        # fleet that intends to pool results cannot allow that silently.
        raise SystemExit(
            "This config sets fleet.forbid_auto_profile. Pass --target-tokens "
            "or --profile explicitly, or set target_tokens in the config file."
        )

    registry = OllamaModelRegistry()

    try:
        info = registry.inspect(model_name)
    except Exception:  # noqa: BLE001 - auto-sizing is a convenience, not a gate
        logger.warning(
            "Could not inspect %s for auto-sizing; falling back to the standard profile.",
            model_name,
        )
        return PROFILES["standard"]

    bytes_per_element = 1 if kv_cache_type == "q8_0" else 2

    feasible = recommend_target_tokens(info, bytes_per_element=bytes_per_element)

    # Auto-sizing changes what is measured, so it is never silent.
    print(
        f"Auto-sized sweep for {model_name} on this machine: "
        + ", ".join(f"{size:,}" for size in feasible)
    )
    print("  (override with --target-tokens or --profile)")
    print()

    return feasible


def _build_config(
    args: argparse.Namespace,
    spec: ExperimentSpec,
    model_name: str,
    settings: ResolvedSettings,
) -> RunConfig:
    """Layer dataclass defaults, then the config file, then CLI flags.

    Written as one function rather than spread across the sections so the
    precedence order is readable in one place: each _pick() call reads
    left-to-right as "CLI, then file, then dataclass default".
    """

    experiment = settings.experiment
    machine = settings.machine

    sweep_defaults = SweepConfig()
    execution_defaults = ExecutionConfig()
    judge_defaults = JudgeConfig()
    embedding_defaults = EmbeddingConfig()
    tokenizer_defaults = TokenizerConfig()

    kv_cache_type = _pick(args.kv_cache_type, experiment.kv_cache_type, "f16")

    target_tokens = _resolve_target_tokens(args, settings, model_name, kv_cache_type)

    judge_model = _pick(args.judge_model, experiment.judge_model)

    if settings.fleet.require_explicit_judge and not args.no_judge and not judge_model:
        # LIMITATIONS 1.2: the default judge IS the generation model, and a
        # self-judged llm_judge column is not reportable no matter how it
        # scores. A fleet that intends to publish cannot default into it.
        raise SystemExit(
            "This config sets fleet.require_explicit_judge. Pass --judge-model, "
            "set judge_model in the config file, or pass --no-judge."
        )

    return RunConfig(
        benchmark_family=spec.family,
        experiment=spec.name,
        generation_model=model_name,
        requested_context_window=args.context,
        tokenizer=TokenizerConfig(
            provider=tokenizer_defaults.provider,
            name=_pick(args.tokenizer, experiment.tokenizer_name, tokenizer_defaults.name),
        ),
        embedding=EmbeddingConfig(
            enabled=(
                False
                if args.no_embedding
                else _pick(experiment.embedding_enabled, embedding_defaults.enabled)
            ),
            provider=embedding_defaults.provider,
            model=_pick(
                args.embedding_model,
                experiment.embedding_model,
                embedding_defaults.model,
            ),
        ),
        judge=JudgeConfig(
            enabled=(
                False if args.no_judge else _pick(experiment.judge_enabled, judge_defaults.enabled)
            ),
            provider=judge_defaults.provider,
            model=judge_model,
            num_ctx=_pick(args.judge_context, experiment.judge_num_ctx, judge_defaults.num_ctx),
        ),
        sweep=SweepConfig(
            target_tokens=target_tokens,
            depths=_pick(args.depths, experiment.depths, sweep_defaults.depths),
            needles_per_configuration=_pick(
                args.needles,
                experiment.needles_per_configuration,
                sweep_defaults.needles_per_configuration,
            ),
            context_buffer_tokens=_pick(
                experiment.context_buffer_tokens,
                sweep_defaults.context_buffer_tokens,
            ),
        ),
        execution=ExecutionConfig(
            continue_on_error=not args.fail_fast,
            two_phase=(
                False
                if args.single_phase
                else _pick(machine.two_phase, execution_defaults.two_phase)
            ),
            sort_cases_by_num_ctx=_pick(
                machine.sort_cases_by_num_ctx,
                execution_defaults.sort_cases_by_num_ctx,
            ),
            keep_alive=_pick(machine.keep_alive, execution_defaults.keep_alive),
            max_retries=_pick(machine.max_retries, execution_defaults.max_retries),
            retry_backoff_sec=_pick(
                machine.retry_backoff_sec,
                execution_defaults.retry_backoff_sec,
            ),
            enforce_memory_preflight=(
                False
                if args.skip_memory_check
                else _pick(
                    machine.enforce_memory_preflight,
                    execution_defaults.enforce_memory_preflight,
                )
            ),
            memory_headroom_fraction=_pick(
                machine.memory_headroom_fraction,
                execution_defaults.memory_headroom_fraction,
            ),
            kv_cache_bytes_per_element=1 if kv_cache_type == "q8_0" else 2,
            kv_cache_type=kv_cache_type,
            think=experiment.think,
            dry_run=args.dry_run,
        ),
        output_dir=_pick(args.output_dir, machine.output_dir, "results"),
        experiment_params=dict(experiment.params),
        metadata={"settings": settings.provenance()},
    )


def _prepare(
    args: argparse.Namespace,
    specs: list[ExperimentSpec],
    model_name: str,
    settings: ResolvedSettings,
) -> None:
    """Health checks and model installation, shared by `run` and `all`.

    Takes the resolved settings rather than reading args directly, so it checks
    the models and paths the run will ACTUALLY use. Before the config layer it
    read argparse defaults, which silently ignored anything the file said.
    """

    if args.skip_health_check:
        return

    required = [model_name]

    if not args.no_judge:
        required.append(_pick(args.judge_model, settings.experiment.judge_model) or model_name)

    if not args.no_embedding:
        required.append(
            _pick(
                args.embedding_model,
                settings.experiment.embedding_model,
                EmbeddingConfig().model,
            )
        )

    ok = _health_and_install(
        required_models=required,
        data_files=required_data_files(specs),
        tokenizer_name=_pick(
            args.tokenizer,
            settings.experiment.tokenizer_name,
            TokenizerConfig().name,
        ),
        output_dir=_pick(args.output_dir, settings.machine.output_dir, "results"),
        assume_yes=args.yes,
    )

    if not ok:
        print(
            "Environment is not ready. Fix the failures above, or re-run with "
            "--skip-health-check to try anyway.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _summarize_output(path: Path) -> None:
    """Print mean metrics per context length from a raw results file."""

    if not path.is_file():
        return

    rows: list[dict] = []

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  Could not read results: {exc}", file=sys.stderr)
        return

    if not rows:
        print("  No results were written.")
        return

    statuses: dict[str, int] = {}

    for row in rows:
        status = row.get("response", {}).get("status", "ok")
        statuses[status] = statuses.get(status, 0) + 1

    print("  Cases: " + ", ".join(f"{count} {name}" for name, count in sorted(statuses.items())))

    grouped: dict[int, list[dict]] = {}

    for row in rows:
        context_tokens = row.get("case", {}).get("context_tokens", 0)
        grouped.setdefault(context_tokens, []).append(row)

    present = [
        metric for metric in METRIC_COLUMNS if any(metric in row.get("metrics", {}) for row in rows)
    ]

    if not present:
        return

    header = f"  {'context':>10}  " + "  ".join(f"{metric:>20}" for metric in present)
    print()
    print(header)
    print("  " + "-" * (len(header) - 2))

    for context_tokens in sorted(grouped):
        cells = []
        case_count = len(grouped[context_tokens])

        for metric in present:
            # Absent metrics mean the evaluator failed; averaging over the
            # ones that succeeded is honest, scoring failures as 0 is not.
            values = [
                row["metrics"][metric]
                for row in grouped[context_tokens]
                if metric in row.get("metrics", {})
            ]

            if not values:
                cells.append(f"{'n/a':>20}")
                continue

            mean = sum(values) / len(values)

            # Disclosing N is the other half of averaging over survivors: a
            # mean over 2 of 3 cases must not print identically to a mean over
            # 3 (LIMITATIONS 1.7). Only annotated when they differ, so the
            # common case stays readable.
            cell = f"{mean:.3f}"

            if len(values) < case_count:
                cell = f"{cell} (n={len(values)}/{case_count})"

            cells.append(f"{cell:>20}")

        print(f"  {context_tokens:>10,}  " + "  ".join(cells))

    print()


def _execute(
    args: argparse.Namespace,
    specs: list[ExperimentSpec],
    model_name: str,
) -> None:
    """Run each selected experiment and report where the results landed."""

    settings = load_settings(
        path=args.config,
        machine_name=args.machine,
        experiment_name=args.experiment_profile,
    )

    _prepare(args, specs, model_name, settings)

    # A configuration that changes what is measured is never silent - the same
    # discipline as printing the auto-sized sweep.
    if settings.source_path is not None:
        print(
            f"Config: {settings.source_path}"
            f" [machine={settings.machine_name or '-'}"
            f" experiment={settings.experiment_name or 'defaults'}]"
        )
        print()

    outputs: list[tuple[ExperimentSpec, Path | None, str | None]] = []

    for index, spec in enumerate(specs, start=1):
        print("=" * 60)
        print(f"[{index}/{len(specs)}] {spec.key}")
        print("=" * 60)

        config = _build_config(args, spec, model_name, settings)

        try:
            output_path = spec.runner(config)
            outputs.append((spec, output_path, None))

        except Exception as exc:  # noqa: BLE001 - one experiment must not kill the rest
            logger.exception("Experiment %s failed", spec.key)
            outputs.append((spec, None, f"{type(exc).__name__}: {exc}"))

    print()
    print("=" * 60)
    print(f"Summary for {model_name}")
    print("=" * 60)

    for spec, output_path, error in outputs:
        print()
        print(f"{spec.key}:")

        if error:
            print(f"  FAILED - {error}")
            continue

        print(f"  Raw results: {output_path}")

        if output_path is not None and not args.dry_run:
            _summarize_output(output_path)

    if any(error for _, _, error in outputs):
        raise SystemExit(1)


def run_all(args: argparse.Namespace) -> None:

    specs = resolve_experiments(args.experiments)

    _execute(args, specs, args.model)


def run_experiment(
    args: argparse.Namespace,
) -> None:

    spec = get_experiment(args.benchmark, args.experiment)

    _execute(args, [spec], args.model)


# =====================================================
# entry point
# =====================================================


def _normalize_argv(argv: list[str]) -> list[str]:
    """Allow `probebench <model>` as shorthand for `probebench all <model>`."""

    if not argv:
        return argv

    first = argv[0]

    if first in KNOWN_COMMANDS or first.startswith("-"):
        return argv

    return ["all", *argv]


def main() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args(_normalize_argv(sys.argv[1:]))

    try:
        _dispatch(args, parser)
    except ConfigError as exc:
        # A malformed config is a user error, not a crash. A traceback here
        # buries the one line that says which key was wrong, which is the
        # entire point of validating the file (D-016).
        print(f"\nConfig error: {exc}\n", file=sys.stderr)
        raise SystemExit(2) from None


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:

    if args.command == "models":
        if args.models_command == "list":
            list_models()
            return

        if args.models_command == "inspect":
            inspect_model(args.model)
            return

        if args.models_command == "pull":
            pull_model_command(args.model, args.yes)
            return

    if args.command == "experiments" and args.experiments_command == "list":
        list_experiments()
        return

    if args.command == "doctor":
        doctor_command(args)
        return

    if args.command == "plan":
        plan_command(args)
        return

    if args.command == "all":
        run_all(args)
        return

    if args.command == "run":
        run_experiment(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
