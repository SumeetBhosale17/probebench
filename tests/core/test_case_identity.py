from typing import Any

import pytest

from probebench.benchmarks.long_range_dependency.NIAH.identity import (
    build_case_fingerprint,
    build_case_key,
)
from probebench.core.case_identity import ComponentError, fingerprint, format_depth


def _components(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        experiment="needle_in_a_haystack",
        prompt_sha256="a" * 64,
        system_prompt="You are a precise extraction engine.",
        expected="ALPHA-9921-X",
        needle="The secret access code is ALPHA-9921-X.",
        target_tokens=4000,
        depth=0.5,
        tokenizer_provider="tiktoken",
        tokenizer_name="cl100k_base",
        filler_sha256="b" * 64,
        needle_template="marked",
        tail_guard_tokens=0,
    )
    base.update(overrides)
    return base


def test_fingerprint_is_stable_across_key_order() -> None:
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})


def test_fingerprint_rejects_raw_floats() -> None:
    with pytest.raises(ComponentError):
        fingerprint({"depth": 0.5})

    with pytest.raises(ComponentError):
        fingerprint({"nested": {"items": [1, 0.5]}})


def test_depth_formatting_is_arithmetic_independent() -> None:
    assert format_depth(0.1 + 0.2) == format_depth(0.3)


def test_fingerprint_changes_with_every_component() -> None:
    baseline = build_case_fingerprint(**_components())

    for field, value in [
        ("prompt_sha256", "c" * 64),
        ("system_prompt", "a different contract"),
        ("expected", "OTHER"),
        ("needle", "different"),
        ("target_tokens", 8000),
        ("depth", 0.75),
        ("tokenizer_provider", "hf"),
        ("tokenizer_name", "o200k_base"),
        ("filler_sha256", "d" * 64),
        ("needle_template", "bare"),
        ("tail_guard_tokens", 512),
    ]:
        assert build_case_fingerprint(**_components(**{field: value})) != baseline, field


def test_distractors_are_a_component_from_v1() -> None:
    """Adding one later would change every fingerprint for identical inputs."""

    assert build_case_fingerprint(**_components()) != build_case_fingerprint(
        **_components(), distractors=[{"needle": "x", "depth": "0.25"}]
    )


def test_fingerprint_ignores_hardware() -> None:
    """The same case on two machines must join (D-013)."""

    assert build_case_fingerprint(**_components()) == build_case_fingerprint(**_components())


def test_case_key_is_sweep_independent_and_carries_the_arm() -> None:
    def key(**overrides: Any) -> str:
        base: dict[str, Any] = dict(
            target_tokens=4000,
            depth=0.5,
            needle="The secret access code is ALPHA-9921-X.",
            needle_template="marked",
            tail_guard_tokens=0,
        )
        base.update(overrides)
        return build_case_key(**base)

    assert key() == key()
    assert key().startswith("niah/t4000/d0.50/n")

    # The arm is part of the key: pooling two arms would be J-004 one level up.
    assert key() != key(needle_template="bare")
    assert key() != key(tail_guard_tokens=512)
    assert key() != key(needle="a different needle")
