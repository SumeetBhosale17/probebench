"""Layered run settings: config file, environment, command line.

Precedence, most specific wins:

    CLI flag  >  environment  >  [machine.<name>] / [experiment.<name>]
              >  [defaults]   >  dataclass defaults in core/config.py

[machine.*] and [experiment.*] are DISJOINT rather than ordered against each
other. A machine section may only carry keys that change how a run executes; an
experiment section may only carry keys that change what is measured. That split
is the reason the file exists: if a machine profile could set `depths`, the
same command would measure different things on different boxes, which is
LIMITATIONS 1.6 with a config file in front of it (D-016).

No environment variable may set a measured parameter, and this module has no
code path by which one could. An env var is invisible in shell history,
invisible in a config diff, and absent from the record unless something
captures it explicitly - the same mechanism as LIMITATIONS 1.12, with a weaker
audit trail.

tomllib is read-only and that is deliberate. Nothing here writes TOML: the file
is hand-edited and reviewed, so a writer would add a dependency and a second,
drifting representation of the same state.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONFIG_ENV_VAR = "PROBEBENCH_CONFIG"
MACHINE_ENV_VAR = "PROBEBENCH_MACHINE"

# Searched upward from the working directory, nearest first, so a run inherits
# the config of the tree it was launched in rather than of $HOME.
CONFIG_FILENAMES = ("probebench.toml", ".probebench.toml")


class ConfigError(ValueError):
    """A config file is missing, malformed, or names an unknown section."""


class StrictSection(BaseModel):
    """Base for every section.

    extra="forbid" is load-bearing, not tidiness. A silently ignored typo
    (`dephts = [0.0, 0.5]`) is a run that measured something other than what
    the file says, and once it is in the archive it is indistinguishable from
    a correct run. Rejecting unknown keys is the whole safety argument.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class ExperimentSection(StrictSection):
    """Keys that change WHAT IS MEASURED.

    Nothing here may come from an environment variable, and nothing here may be
    set by a [machine.*] section.

    kv_cache_type lives here rather than in MachineSection even though it looks
    like a memory knob: whether q8_0 KV degrades retrieval is UNMEASURED, so
    until it is measured it is a measured variable and must be pinned across
    the fleet like any other (D-016).
    """

    target_tokens: list[int] | None = None
    depths: list[float] | None = None
    needles_per_configuration: int | None = None
    context_buffer_tokens: int | None = None
    tokenizer_name: str | None = None

    kv_cache_type: Literal["f16", "q8_0"] | None = None

    # Reasoning changes the output distribution at fixed input, so it is a
    # measured variable (J-017). None leaves the model at its own default.
    think: bool | None = None

    judge_enabled: bool | None = None
    judge_model: str | None = None
    judge_num_ctx: int | None = None
    embedding_enabled: bool | None = None
    embedding_model: str | None = None

    # Benchmark-specific construction knobs, carried opaquely. CLAUDE.md's
    # scope rule is that anything in core/ mentioning needles is in the wrong
    # place, so filler_path / question / needle_template are NOT fields here -
    # they are validated against a model owned by the benchmark package.
    params: dict[str, Any] = Field(default_factory=dict)


class MachineSection(StrictSection):
    """Keys that change only HOW A RUN EXECUTES.

    Deliberately tiny. If a key is arguable, it belongs in [experiment.*] - a
    machine profile that changes what is measured is the failure this split
    exists to make unrepresentable.
    """

    memory_headroom_fraction: float | None = None
    enforce_memory_preflight: bool | None = None
    two_phase: bool | None = None
    sort_cases_by_num_ctx: bool | None = None
    keep_alive: str | None = None
    max_retries: int | None = None
    retry_backoff_sec: float | None = None
    output_dir: str | None = None


class FleetSection(StrictSection):
    """Constraints the whole fleet agrees to, checked at load time."""

    # LIMITATIONS 1.6: --profile auto sizes the sweep from THIS host's free RAM,
    # so two machines produce different sweeps for the same command. A fleet
    # that intends to pool results cannot allow it.
    forbid_auto_profile: bool = False

    # LIMITATIONS 1.2: the default judge IS the generation model, and a
    # self-judged llm_judge column is not reportable however well it scores.
    require_explicit_judge: bool = False

    # Name of the [experiment.*] section every machine runs as an instrument
    # check before a long run.
    calibration: str | None = None


class ProbeBenchFile(StrictSection):
    """The whole file."""

    fleet: FleetSection = Field(default_factory=FleetSection)
    defaults: ExperimentSection = Field(default_factory=ExperimentSection)
    machine: dict[str, MachineSection] = Field(default_factory=dict)
    experiment: dict[str, ExperimentSection] = Field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedSettings:
    """The file layer, flattened. CLI overrides are applied on top of this."""

    experiment: ExperimentSection
    machine: MachineSection
    fleet: FleetSection

    source_path: Path | None
    machine_name: str | None
    experiment_name: str | None

    def provenance(self) -> dict[str, Any]:
        """What a record should carry about this resolution."""

        return {
            "config_path": str(self.source_path) if self.source_path else None,
            "config_machine": self.machine_name,
            "config_experiment": self.experiment_name,
        }


def overlay[SectionT: StrictSection](base: SectionT, over: SectionT) -> SectionT:
    """Field-wise overlay. A field set in `over` wins; None means "not set".

    None is the only "unset" marker in the whole layering, because a config
    layer must be able to stay silent about a key. That is also why every field
    above is optional.
    """

    merged = dict(base.model_dump())

    for key, value in over.model_dump().items():
        if value is None:
            continue

        # `params` merges rather than replaces, so a per-experiment section can
        # override one benchmark knob without restating the defaults block.
        if key == "params" and isinstance(value, dict):
            merged_params = dict(merged.get("params") or {})
            merged_params.update(value)
            merged["params"] = merged_params
            continue

        merged[key] = value

    return type(base)(**merged)


def find_config_file(start_dir: Path | None = None) -> Path | None:
    """Nearest probebench.toml at or above `start_dir`, or None."""

    current = (start_dir or Path.cwd()).resolve()

    for directory in (current, *current.parents):
        for name in CONFIG_FILENAMES:
            candidate = directory / name

            if candidate.is_file():
                return candidate

    return None


def load_settings(
    *,
    path: str | None = None,
    machine_name: str | None = None,
    experiment_name: str | None = None,
    start_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> ResolvedSettings:
    """Resolve the file layer.

    `environ` is injected rather than read from os.environ directly so the
    precedence rules are testable without mutating process state.
    """

    env = environ if environ is not None else dict(os.environ)

    if path is None:
        path = env.get(CONFIG_ENV_VAR)
        explicit = False
    else:
        explicit = True

    if path is not None:
        config_path: Path | None = Path(path).expanduser()

        # A path the user typed that does not exist is an error. Silently
        # ignoring it is how a run measures something other than what was asked
        # for. A merely discovered file being absent is not an error.
        if config_path is not None and not config_path.is_file():
            if explicit:
                raise ConfigError(f"Config file not found: {path}")

            config_path = None
    else:
        config_path = find_config_file(start_dir)

    if config_path is None:
        return ResolvedSettings(
            experiment=ExperimentSection(),
            machine=MachineSection(),
            fleet=FleetSection(),
            source_path=None,
            machine_name=None,
            experiment_name=None,
        )

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not parse {config_path}: {exc}") from exc

    try:
        parsed = ProbeBenchFile(**raw)
    except ValidationError as exc:
        # Surfaced verbatim: pydantic names the offending key and section,
        # which is the entire value of extra="forbid".
        raise ConfigError(f"Invalid config in {config_path}:\n{exc}") from exc

    resolved_machine_name = machine_name or env.get(MACHINE_ENV_VAR) or None

    machine = MachineSection()

    if resolved_machine_name is not None:
        if resolved_machine_name not in parsed.machine:
            known = ", ".join(sorted(parsed.machine)) or "<none defined>"

            raise ConfigError(
                f"Unknown machine '{resolved_machine_name}' in {config_path}. Known: {known}"
            )

        machine = parsed.machine[resolved_machine_name]

    experiment = parsed.defaults

    if experiment_name is not None:
        if experiment_name not in parsed.experiment:
            known = ", ".join(sorted(parsed.experiment)) or "<none defined>"

            raise ConfigError(
                f"Unknown experiment profile '{experiment_name}' in {config_path}. Known: {known}"
            )

        experiment = overlay(parsed.defaults, parsed.experiment[experiment_name])

    return ResolvedSettings(
        experiment=experiment,
        machine=machine,
        fleet=parsed.fleet,
        source_path=config_path,
        machine_name=resolved_machine_name,
        experiment_name=experiment_name,
    )
