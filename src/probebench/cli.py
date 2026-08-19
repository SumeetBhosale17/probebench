import argparse
import logging
import sys

from probebench.core.config import (
    EmbeddingConfig,
    JudgeConfig,
    RunConfig,
    TokenizerConfig,
)
from probebench.experiments.long_range_dependency.NIAH.run import (
    run_niah,
)
from probebench.models.registry import (
    OllamaModelRegistry,
)


def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="probebench",
        description=("ProbeBench LLM benchmarking framework."),
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
    # run
    # -------------------------------------------------

    run_parser = subparsers.add_parser(
        "run",
        help="Run a benchmark experiment.",
    )

    run_parser.add_argument(
        "--benchmark",
        required=True,
        choices=[
            "long_range_dependency",
        ],
    )

    run_parser.add_argument(
        "--experiment",
        required=True,
        choices=[
            "NIAH",
        ],
    )

    run_parser.add_argument(
        "--model",
        required=True,
        help="Generation model.",
    )

    run_parser.add_argument(
        "--context",
        type=int,
        default=None,
        help=("Requested model context window. Example: 32000."),
    )

    run_parser.add_argument(
        "--tokenizer",
        default="cl100k_base",
        help="Tokenizer encoding.",
    )

    run_parser.add_argument(
        "--embedding-model",
        default="nomic-embed-text",
        help="Embedding model.",
    )

    run_parser.add_argument(
        "--judge-model",
        default=None,
        help="LLM judge model.",
    )

    return parser


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


def list_experiments() -> None:

    print("Available ProbeBench Experiments")
    print("=" * 60)

    print("long_range_dependency")
    print("    └── NIAH")


def run_experiment(
    args: argparse.Namespace,
) -> None:

    if args.benchmark == "long_range_dependency" and args.experiment == "NIAH":
        config = RunConfig(
            benchmark_family=(args.benchmark),
            experiment=args.experiment,
            generation_model=args.model,
            requested_context_window=(args.context),
            tokenizer=TokenizerConfig(
                provider="tiktoken",
                name=args.tokenizer,
            ),
            embedding=EmbeddingConfig(
                enabled=True,
                provider="ollama",
                model=args.embedding_model,
            ),
            judge=JudgeConfig(
                enabled=True,
                provider="ollama",
                model=args.judge_model,
            ),
        )

        output_path = run_niah(config)

        print()
        print(f"Raw results: {output_path}")

        return

    raise ValueError("Unsupported benchmark/experiment combination.")


def main() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "models":
        if args.models_command == "list":
            list_models()
            return

        if args.models_command == "inspect":
            inspect_model(args.model)
            return

    if args.command == "experiments" and args.experiments_command == "list":
        list_experiments()
        return

    if args.command == "run":
        run_experiment(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
