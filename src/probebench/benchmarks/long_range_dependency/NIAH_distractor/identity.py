"""Case identity for the keyed distractor family (D-012, invariant 11).

Separate from NIAH's because the two experiments have different design points.
Sharing one builder would force a single key format to describe both, and the
segment that matters here - which decoys were planted where - has no meaning in
NIAH.
"""

from typing import Any

from probebench.core.case_identity import (
    fingerprint,
    format_depth,
    sha256_text,
    short_digest,
)

CASE_KEY_PREFIX = "niahd"


def background_digest(background: list[dict[str, Any]]) -> str:
    """Address the decoy layout by content.

    Two cases with the same target, depth and k but different decoys are
    DIFFERENT design points - the decoys are the independent variable, not
    scaffolding. A key that pooled them would be J-004 one level up, so the
    layout is hashed into the key rather than summarised by its size.

    Depths are pre-formatted strings here, as everywhere: a float in a digest
    makes the address depend on how a number was arrived at (`_reject_floats`).
    """

    return short_digest(
        "|".join(f"{item['id']}@{item['depth']}" for item in background),
        length=8,
    )


def build_case_key(
    *,
    target_tokens: int,
    depth: float,
    target_id: str,
    background: list[dict[str, Any]],
    needle_template: str,
    tail_guard_tokens: int,
) -> str:
    """The sweep-independent grid coordinate for one distractor case.

    Carries no counter (J-004). The target is named by its stable `id` rather
    than by a digest of its sentence: unlike NIAH's free-text needles, a keyed
    needle HAS a stable identifier, and `brightwater` in a key is readable where
    `n06bfb731` is not. The value is still content-addressed - through
    `case_fingerprint`, which is where a changed code must show up.

    `k` is redundant given the background digest and is carried anyway, because
    the most common slice of this experiment is "hold k, vary depth" and a key
    that requires a join to answer it is a key people will stop using.
    """

    return (
        f"{CASE_KEY_PREFIX}"
        f"/t{target_tokens}"
        f"/d{format_depth(depth)}"
        f"/k{len(background)}"
        f"/s{target_id}"
        f"/b{background_digest(background)}"
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

    The SAME component set as NIAH's, with `distractors` finally populated -
    the slot D-012 pre-registered three schema versions ago against exactly this
    day, so no FINGERPRINT_VERSION bump is needed and the two families remain
    comparable as component sets even though their keys differ.

    `experiment` differs between the families, so a NIAH case and a distractor
    case can never collide on a fingerprint even at k=0, where the two are
    otherwise structurally identical.
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
