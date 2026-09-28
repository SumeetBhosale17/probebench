"""Interactive installation of missing Ollama models.

Pulling a model downloads gigabytes over the network, so it is never done
silently. The default is to ask; --yes opts in ahead of time; a
non-interactive shell refuses rather than guessing.
"""

import logging
import sys

import ollama

from probebench.models.host import default_ollama_host

logger = logging.getLogger(__name__)

MIB = 1024 * 1024


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def confirm_install(models: list[str], assume_yes: bool = False) -> bool:
    """Ask whether to pull the missing models.

    Returns False in a non-interactive shell unless assume_yes was passed,
    so an unattended run never starts a multi-gigabyte download on its own.
    """

    if not models:
        return False

    if assume_yes:
        return True

    if not _is_interactive():
        print(
            "Missing models: "
            + ", ".join(models)
            + "\nNot running interactively, so nothing was downloaded."
            + "\nRe-run with --yes to allow ProbeBench to pull them, or run "
            + "`ollama pull <model>` yourself."
        )
        return False

    print()
    print("The following models are required but not installed:")

    for model in models:
        print(f"  - {model}")

    print()
    print("ProbeBench can download them now with `ollama pull`.")
    print("This may take several minutes and use several GB of disk.")

    try:
        answer = input("Install them now? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    return answer in {"y", "yes"}


def pull_model(
    model: str,
    host: str | None = None,
) -> None:
    """Pull one model, printing progress on a single line."""

    client = ollama.Client(host=host or default_ollama_host())

    print(f"Pulling {model} ...")

    last_status = ""

    try:
        for chunk in client.pull(model, stream=True):
            status = chunk.get("status", "")
            completed = chunk.get("completed")
            total = chunk.get("total")

            if completed and total:
                percent = 100.0 * completed / total

                sys.stdout.write(
                    f"\r  {status}: {percent:5.1f}% "
                    f"({completed / MIB:.0f}/{total / MIB:.0f} MiB)   "
                )
                sys.stdout.flush()

            elif status and status != last_status:
                sys.stdout.write(f"\r  {status}                              ")
                sys.stdout.flush()

            last_status = status

    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        sys.stdout.write("\n")
        raise RuntimeError(f"Failed to pull '{model}': {exc}") from exc

    sys.stdout.write(f"\r  {model}: done                              \n")
    sys.stdout.flush()


def install_missing_models(
    models: list[str],
    *,
    assume_yes: bool = False,
    host: str | None = None,
) -> list[str]:
    """Offer to install missing models. Returns the ones still missing."""

    if not models:
        return []

    if not confirm_install(models, assume_yes=assume_yes):
        return list(models)

    still_missing: list[str] = []

    for model in models:
        try:
            pull_model(model, host=host)
        except RuntimeError as exc:
            logger.error("%s", exc)
            still_missing.append(model)

    return still_missing
