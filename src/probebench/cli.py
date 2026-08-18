import argparse
import sys

from probebench.models.registry import (
    OllamaModelRegistry
)

def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="probebench",
        description=(
            "ProbeBench LLM benchmarking framework."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command"
    )

    # -------------------------------------------------
    # models
    # -------------------------------------------------

    model_parser = subparsers.add_parser(
        "models",
        help="Manage and inspect local models."
    )

    models_subparsers = (
        model_parser.add_subparsers(
            dest="models_command"
        )
    )

    models_subparsers.add_parser(
        "list",
        help="List installed Ollama models."
    )

    inspect_parser = (
        models_subparsers.add_parser(
            "inspect",
            help="Inspect an Ollama model."
        )
    )

    inspect_parser.add_argument(
        "model",
        help="Model name, e.g. llama3.1:8b"
    )

    return parser

def list_models() -> None:

    registry = OllamaModelRegistry()

    try:
        models = registry.list_models()

    except Exception as exc:
        print(
            f"failed to connect to Ollama: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not models:
        print("No Ollama Models found.")
        return 

    print("Installed Ollama Models")
    print("=" * 60)

    for index, model in enumerate(
        models,
        start=1
    ):
        print(
            f"{index}. {model.name}"
        )

        if model.family:
            print(
                f"    Family: {model.family}"
            )

        if model.parameter_size:
            print(
                f"    Parameters: "
                f"{model.parameter_size}"
            )

        if model.quantization:
            print(
                f"    Quantization: "
                f"{model.quantization}"
            )

        print()

def inspect_model(
        model_name: str,
) -> None:

    registry = OllamaModelRegistry()

    try:
        info = registry.inspect(model_name)

    except Exception as exc:
        print(
            f"Failed to inspect '{model_name}': "
            f"{exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"Model:              {info.name}")
    print(
        f"Family:             "
        f"{info.family or 'unknown'}"
    )
    print(
        f"Parameters:         "
        f"{info.parameter_size or 'unknown'}"
    )
    print(
        f"Quantization:       "
        f"{info.quantization or 'unknown'}"
    )

    context = (
        f"{info.context_length:,}"
        if info.context_length
        else "unknown"
    )

    print(
        f"Supported context:  {context}"
    )

    capabilities = (
        ", ".join(info.capabilities)
        if info.capabilities
        else "unknown"
    )

    print(
        f"Capabilities:       {capabilities}"
    )

    print(
        f"Tokenizer model:    "
        f"{info.tokenizer_model or 'unknown'}"
    )

    print(
        f"Tokenizer pre:      "
        f"{info.tokenizer_pre or 'unknown'}"
    )


def main() -> None:

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "models":

        if args.models_command == "list":
            list_models()
            return

        if args.models_command == "inspect":
            inspect_model(args.model)
            return

    parser.print_help()


if __name__ == "__main__":
    main()