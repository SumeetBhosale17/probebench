from pathlib import Path

import pytest

from probebench.core.settings import (
    ConfigError,
    ExperimentSection,
    load_settings,
    overlay,
)

FILE = """
[fleet]
forbid_auto_profile = true

[defaults]
depths = [0.0, 0.5, 1.0]
needles_per_configuration = 6
params = { question = "base question", filler_path = "a.txt" }

[experiment.long]
target_tokens = [32000]
params = { question = "long question" }

[machine.box-a]
two_phase = false
memory_headroom_fraction = 0.8
"""


def _write(tmp_path: Path, text: str = FILE) -> Path:
    path = tmp_path / "probebench.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_absent_config_yields_empty_sections(tmp_path: Path) -> None:
    settings = load_settings(start_dir=tmp_path, environ={})

    assert settings.source_path is None
    assert settings.experiment.depths is None


def test_an_explicit_missing_path_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(path=str(tmp_path / "nope.toml"), environ={})


def test_unknown_key_is_rejected_by_name(tmp_path: Path) -> None:
    """A silently ignored typo is worse than no config file at all."""

    path = _write(tmp_path, "[defaults]\ndephts = [0.0]\n")

    with pytest.raises(ConfigError) as excinfo:
        load_settings(path=str(path), environ={})

    assert "dephts" in str(excinfo.value)


def test_experiment_profile_overlays_defaults(tmp_path: Path) -> None:
    settings = load_settings(path=str(_write(tmp_path)), experiment_name="long", environ={})

    assert settings.experiment.target_tokens == [32000]
    # Inherited from [defaults] rather than reset by the profile.
    assert settings.experiment.depths == [0.0, 0.5, 1.0]


def test_params_merge_rather_than_replace(tmp_path: Path) -> None:
    settings = load_settings(path=str(_write(tmp_path)), experiment_name="long", environ={})

    assert settings.experiment.params["question"] == "long question"
    assert settings.experiment.params["filler_path"] == "a.txt"


def test_unknown_section_names_are_errors(tmp_path: Path) -> None:
    path = _write(tmp_path)

    with pytest.raises(ConfigError):
        load_settings(path=str(path), machine_name="no-such-box", environ={})

    with pytest.raises(ConfigError):
        load_settings(path=str(path), experiment_name="no-such-profile", environ={})


def test_machine_section_cannot_carry_a_measured_key(tmp_path: Path) -> None:
    """D-016: the measured/operational split is a type error, not a convention."""

    path = _write(tmp_path, "[machine.box-a]\ndepths = [0.0]\n")

    with pytest.raises(ConfigError):
        load_settings(path=str(path), machine_name="box-a", environ={})


def test_env_supplies_the_machine_name_but_never_a_measured_key(tmp_path: Path) -> None:
    settings = load_settings(
        path=str(_write(tmp_path)),
        environ={"PROBEBENCH_MACHINE": "box-a"},
    )

    assert settings.machine_name == "box-a"
    assert settings.machine.two_phase is False

    # There is no env var that could have set this, by construction.
    assert settings.experiment.depths == [0.0, 0.5, 1.0]


def test_overlay_treats_none_as_unset() -> None:
    base = ExperimentSection(depths=[0.0], needles_per_configuration=6)
    over = ExperimentSection(depths=[1.0])

    merged = overlay(base, over)

    assert merged.depths == [1.0]
    assert merged.needles_per_configuration == 6


def test_repo_config_file_parses() -> None:
    """The committed probebench.toml must load, or the fleet is broken."""

    repo_config = Path(__file__).resolve().parents[2] / "probebench.toml"

    settings = load_settings(path=str(repo_config), experiment_name="calibration", environ={})

    assert settings.experiment.target_tokens == [4000]
    assert settings.fleet.calibration == "calibration"
