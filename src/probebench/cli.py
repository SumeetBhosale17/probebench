import argparse
import json
import logging
import sys
from pathlib import Path

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
    "lexical_exact_match",
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
        default="auto",
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
        default=[0.0, 0.25, 0.5, 0.75, 1.0],
        help="Comma-separated needle depths in [0,1].",
    )

    parser.add_argument(
        "--needles",
        type=int,
        default=1,
        help="Needles per (length, depth) configuration.",
    )

    parser.add_argument(
        "--tokenizer",
        default="cl100k_base",
        help="Tokenizer encoding.",
    )

    parser.add_argument(
        "--embedding-model",
        default="nomic-embed-text",
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
        default=4096,
        help="Pinned judge context. Keeping this fixed avoids per-case model reloads.",
    )

    parser.add_argument(
        "--kv-cache-type",
        choices=["f16", "q8_0"],
        default="f16",
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
        default="results",
        help="Directory for raw results.",
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

    print(f"Layers:             {info.block_count or 'unknown'}")

    print(f"KV heads:           {info.kv_head_count or 'unknown'}")

    print(f"Head dim:           {info.head_dim or 'unknown'}")

    per_token = info.kv_bytes_per_token()

    if per_token:
        print(f"KV cache per token: {per_token / 1024:.0f} KiB")


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


def _resolve_target_tokens(
    args: argparse.Namespace,
    model_name: str,
    kv_cache_type: str,
) -> list[int]:
    """Decide the context sweep: explicit list, named profile, or auto-sized."""

    if args.target_tokens:
        return args.target_tokens

    if args.profile != "auto":
        return PROFILES[args.profile]

    registry = OllamaModelRegistry()

    try:
        info = registry.inspect(model_name)
    except Exception:
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
    target_tokens: list[int],
) -> RunConfig:

    return RunConfig(
        benchmark_family=spec.family,
        experiment=spec.name,
        generation_model=model_name,
        requested_context_window=args.context,
        tokenizer=TokenizerConfig(
            provider="tiktoken",
            name=args.tokenizer,
        ),
        embedding=EmbeddingConfig(
            enabled=not args.no_embedding,
            provider="ollama",
            model=args.embedding_model,
        ),
        judge=JudgeConfig(
            enabled=not args.no_judge,
            provider="ollama",
            model=args.judge_model,
            num_ctx=args.judge_context,
        ),
        sweep=SweepConfig(
            target_tokens=target_tokens,
            depths=args.depths,
            needles_per_configuration=args.needles,
        ),
        execution=ExecutionConfig(
            continue_on_error=not args.fail_fast,
            two_phase=not args.single_phase,
            enforce_memory_preflight=not args.skip_memory_check,
            kv_cache_bytes_per_element=1 if args.kv_cache_type == "q8_0" else 2,
            dry_run=args.dry_run,
        ),
        output_dir=args.output_dir,
    )


def _prepare(
    args: argparse.Namespace,
    specs: list[ExperimentSpec],
    model_name: str,
) -> None:
    """Health checks and model installation, shared by `run` and `all`."""

    if args.skip_health_check:
        return

    required = [model_name]

    if not args.no_judge:
        required.append(args.judge_model or model_name)

    if not args.no_embedding:
        required.append(args.embedding_model)

    ok = _health_and_install(
        required_models=required,
        data_files=required_data_files(specs),
        tokenizer_name=args.tokenizer,
        output_dir=args.output_dir,
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

        for metric in present:
            # Absent metrics mean the evaluator failed; averaging over the
            # ones that succeeded is honest, scoring failures as 0 is not.
            values = [
                row["metrics"][metric]
                for row in grouped[context_tokens]
                if metric in row.get("metrics", {})
            ]

            cells.append(f"{sum(values) / len(values):>20.3f}" if values else f"{'n/a':>20}")

        print(f"  {context_tokens:>10,}  " + "  ".join(cells))

    print()


def _execute(
    args: argparse.Namespace,
    specs: list[ExperimentSpec],
    model_name: str,
) -> None:
    """Run each selected experiment and report where the results landed."""

    _prepare(args, specs, model_name)

    target_tokens = _resolve_target_tokens(args, model_name, args.kv_cache_type)

    outputs: list[tuple[ExperimentSpec, Path | None, str | None]] = []

    for index, spec in enumerate(specs, start=1):
        print("=" * 60)
        print(f"[{index}/{len(specs)}] {spec.key}")
        print("=" * 60)

        config = _build_config(args, spec, model_name, target_tokens)

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
