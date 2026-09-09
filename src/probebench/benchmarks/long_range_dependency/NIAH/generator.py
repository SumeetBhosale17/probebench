"""NIAH's case construction: the legacy needle file and its frozen wrapper.

The haystack primitive moved to `long_range_dependency/haystack.py` when the
keyed families arrived. It is re-exported here because the archive, the
byte-identity test and every existing import path name it through this module,
and none of that is worth breaking to tidy an import.
"""

from probebench.benchmarks.long_range_dependency.haystack import (
    MARKED_TEMPLATE,
    Block,
    EncodedFiller,
    Haystack,
    PlacedBlock,
    build_haystack,
    load_filler,
)
from probebench.core.tokenizer import Tokenizer

__all__ = [
    "MARKED_TEMPLATE",
    "Block",
    "EncodedFiller",
    "Haystack",
    "PlacedBlock",
    "build_haystack",
    "count_tokens",
    "create_haystack",
    "extract_expected_answer",
    "load_filler",
    "load_needles",
]


def load_needles(path: str) -> list[str]:
    """Load non-empty needle lines."""

    with open(
        path,
        encoding="utf-8",
    ) as file:
        return [line.strip() for line in file if line.strip()]


def extract_expected_answer(
    needle: str,
) -> str:
    """
    Extract the expected answer from the
    existing needle format.
    """

    if "'" in needle:
        parts = needle.split("'")

        if len(parts) >= 3:
            return parts[1].strip()

    if " is " in needle:
        answer = needle.split(
            " is ",
            maxsplit=1,
        )[1]

        return answer.strip().rstrip(".")

    return needle.strip()


def create_haystack(
    filler: str,
    needle: str,
    target_tokens: int,
    depth: float,
    tokenizer: Tokenizer,
) -> str:
    """
    Create a token-controlled NIAH context.

    depth=0.0 -> beginning
    depth=0.5 -> middle
    depth=1.0 -> end

    Kept with its original signature AND its original output. It is now a thin
    wrapper over build_haystack; the wrapper re-encodes the corpus on every
    call, which is why NiahBenchmark hoists EncodedFiller out of its loop and
    calls build_haystack directly. This survives for callers holding only the
    filler text, and as the shape the archive was built with.
    """

    return build_haystack(
        filler=EncodedFiller.encode(filler, tokenizer),
        blocks=[
            Block(
                block_id="target",
                role="target",
                subject="",
                value=extract_expected_answer(needle),
                text=needle,
                requested_depth=depth,
            )
        ],
        target_tokens=target_tokens,
        tokenizer=tokenizer,
    ).text


def count_tokens(
    text: str,
    tokenizer: Tokenizer,
) -> int:
    """Count tokens using the configured tokenizer."""

    return tokenizer.count(text)
