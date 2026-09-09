"""Case identity for the multi-hop family (D-012, invariant 11).

The distinguishing component is the HOP: which registry entry the pointer names.
Two cases with the same registry and the same pointer depth but different
pointed-to subjects are different design points, and the answer differs, so the
hop is in both keys.
"""

from typing import Any

from probebench.core.case_identity import (
    fingerprint,
    format_depth,
    sha256_text,
    short_digest,
)

CASE_KEY_PREFIX = "niahmh"


def build_case_key(
    *,
    target_tokens: int,
    depth: float,
    pointer_subject: str,
    target_id: str,
    registry: list[dict[str, Any]],
    needle_template: str,
    tail_guard_tokens: int,
) -> str:
    """The sweep-independent grid coordinate for one multi-hop case.

    `depth` is the POINTER's depth. The pointer is what the model must find
    first, and the registry is held fixed across the sweep, so the pointer is
    the position being varied.
    """

    registry_digest = short_digest(
        "|".join(f"{item['id']}@{item['depth']}" for item in registry),
        length=8,
    )

    return (
        f"{CASE_KEY_PREFIX}"
        f"/t{target_tokens}"
        f"/d{format_depth(depth)}"
        f"/k{len(registry)}"
        f"/p{pointer_subject}"
        f"/s{target_id}"
        f"/b{registry_digest}"
        f"/{needle_template}"
        f"/g{tail_guard_tokens}"
    )


def build_case_fingerprint(
    *,
    experiment: str,
    prompt_sha256: str,
    system_prompt: str,
    expected: str,
    needle: str,
    target_tokens: int,
    depth: float,
    tokenizer_provider: str,
    tokenizer_name: str,
    filler_sha256: str,
    needle_template: str,
    tail_guard_tokens: int,
    distractors: list[dict[str, Any]],
) -> str:
    """A content address for everything determining the model's input.

    Identical component set to the other two families - `needle` here is the
    POINTER sentence, which is the block that makes this case what it is, and
    the registry rides in `distractors`. Keeping the set identical is what lets
    a reader compare component sets across families without a per-family decoder.
    """

    return fingerprint(
        {
            "experiment": experiment,
            "prompt_sha256": prompt_sha256,
            "system_prompt_sha256": sha256_text(system_prompt),
            "expected": expected,
            "needle": needle,
            "target_tokens": target_tokens,
            "depth": format_depth(depth),
            "tokenizer_provider": tokenizer_provider,
            "tokenizer_name": tokenizer_name,
            "filler_sha256": filler_sha256,
            "needle_template": needle_template,
            "tail_guard_tokens": tail_guard_tokens,
            "distractors": distractors,
        }
    )
