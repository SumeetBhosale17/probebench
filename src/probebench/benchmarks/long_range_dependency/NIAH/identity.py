"""Which components NIAH's case identity depends on (D-012).

Lives here rather than in core/ because only the benchmark knows what
determines its own input, and CLAUDE.md's scope rule is that anything in
core/ mentioning needles is in the wrong place.
"""

from typing import Any

from probebench.core.case_identity import (
    fingerprint,
    format_depth,
    sha256_text,
    short_digest,
)

CASE_KEY_PREFIX = "niah"


def build_case_key(
    target_tokens: int,
    depth: float,
    needle: str,
    needle_template: str,
    tail_guard_tokens: int,
) -> str:
    """The sweep-independent grid coordinate for a case.

    Carries no counter, so it does not shift when --needles or --depths change
    or when a cell is skipped (J-004).

    It carries the experimental ARM - template and tail guard - because the
    same cell run under two arms is two design points. A key that pooled them
    would be J-004 one level up (D-012).

    The needle is addressed by digest rather than by its line number in
    needles.txt, so reordering that file cannot rename a key, and so the schema
    migration can derive the same key from an archived record without reading
    the file (D-015).
    """

    return (
        f"{CASE_KEY_PREFIX}"
        f"/t{target_tokens}"
        f"/d{format_depth(depth)}"
        f"/n{short_digest(needle)}"
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
    distractors: list[dict[str, Any]] | None = None,
) -> str:
    """A content address for everything determining the model's input.

    The component set is COMPLETE from the first version: needle_template,
    tail_guard_tokens and distractors are hashed now, at their present values,
    even though nothing can vary them yet. Adding a component later would
    change every fingerprint for byte-identical inputs and invalidate the D-009
    cross-model baseline the moment it was captured (D-012).

    Hardware is deliberately NOT a component. The machine does not change the
    model's input, and including it would stop the same case joining across
    machines - which is the comparison the host block exists to enable (D-013).
    """

    return fingerprint(
        {
            "experiment": experiment,
            "prompt_sha256": prompt_sha256,
            "system_prompt_sha256": sha256_text(system_prompt),
            "expected": expected,
            "needle": needle,
            "target_tokens": target_tokens,
            # A string, not the float: 0.1 + 0.2 and 0.3 must not be different
            # components.
            "depth": format_depth(depth),
            "tokenizer_provider": tokenizer_provider,
            "tokenizer_name": tokenizer_name,
            "filler_sha256": filler_sha256,
            "needle_template": needle_template,
            "tail_guard_tokens": tail_guard_tokens,
            "distractors": distractors or [],
        }
    )
