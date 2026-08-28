"""Central registry of runnable experiments.

Adding a new experiment means appending one ExperimentSpec here. The CLI,
the `all` command and the health check all read from this list, so nothing
else needs to change.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from probebench.core.config import RunConfig
from probebench.experiments.long_range_dependency.NIAH.run import run_niah

NIAH_DATA_DIR = "data/long_range_dependency/NIAH"


@dataclass(frozen=True)
class ExperimentSpec:
    """Everything the CLI needs to know to run one experiment."""

    family: str
    name: str
    description: str
    runner: Callable[[RunConfig], Path]

    # Files that must exist before the experiment can build any case.
    data_files: tuple[str, ...] = ()

    # Whether the experiment sweeps context length. Experiments that do not
    # (a future hallucination benchmark, say) skip the memory ladder.
    uses_context_sweep: bool = True

    # Sweep to use when the caller has not asked for a specific one and
    # auto-sizing is disabled.
    default_target_tokens: tuple[int, ...] = field(
        default=(4_000, 8_000, 16_000, 32_000),
    )

    @property
    def key(self) -> str:
        return f"{self.family}/{self.name}"


EXPERIMENTS: tuple[ExperimentSpec, ...] = (
    ExperimentSpec(
        family="long_range_dependency",
        name="NIAH",
        description="Needle in a Haystack: retrieval accuracy vs. context length and depth.",
        runner=run_niah,
        data_files=(
            f"{NIAH_DATA_DIR}/filler_text.txt",
            f"{NIAH_DATA_DIR}/needles.txt",
        ),
        uses_context_sweep=True,
    ),
)


def all_experiments() -> list[ExperimentSpec]:
    """Every registered experiment."""

    return list(EXPERIMENTS)


def get_experiment(family: str, name: str) -> ExperimentSpec:
    """Look up one experiment by family and name."""

    for spec in EXPERIMENTS:
        if spec.family == family and spec.name == name:
            return spec

    known = ", ".join(spec.key for spec in EXPERIMENTS)

    raise ValueError(f"Unknown experiment '{family}/{name}'. Available: {known}")


def resolve_experiments(selectors: list[str] | None) -> list[ExperimentSpec]:
    """Resolve user-supplied selectors into experiment specs.

    A selector is either a bare experiment name ("NIAH") or a fully
    qualified key ("long_range_dependency/NIAH"). None means all of them.
    """

    if not selectors:
        return all_experiments()

    resolved: list[ExperimentSpec] = []

    for selector in selectors:
        if "/" in selector:
            family, _, name = selector.partition("/")
            resolved.append(get_experiment(family, name))
            continue

        matches = [spec for spec in EXPERIMENTS if spec.name == selector]

        if not matches:
            known = ", ".join(spec.key for spec in EXPERIMENTS)
            raise ValueError(f"Unknown experiment '{selector}'. Available: {known}")

        resolved.extend(matches)

    # Preserve order while dropping duplicates.
    return list(dict.fromkeys(resolved))


def required_data_files(specs: list[ExperimentSpec]) -> list[str]:
    """Every data file needed by the given experiments."""

    files: list[str] = []

    for spec in specs:
        files.extend(spec.data_files)

    return list(dict.fromkeys(files))
