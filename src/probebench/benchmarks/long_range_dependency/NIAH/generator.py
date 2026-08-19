from probebench.core.tokenizer import Tokenizer


def load_filler(path: str) -> str:
    """Load filler text from disk."""

    with open(
        path,
        encoding="utf-8",
    ) as file:
        return file.read()


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
    """

    if not 0.0 <= depth <= 1.0:
        raise ValueError(f"Depth must be between 0 and 1, got {depth}")

    filler_tokens = tokenizer.encode(filler)

    needle_text = f"\n\n[IMPORTANT SECRET]: {needle}\n\n"

    needle_tokens = tokenizer.encode(needle_text)

    max_filler_tokens = target_tokens - len(needle_tokens)

    if max_filler_tokens <= 0:
        raise ValueError("Target token count is too small for the needle.")

    limited_filler_tokens = filler_tokens[:max_filler_tokens]

    insertion_index = int(len(limited_filler_tokens) * depth)

    final_tokens = (
        limited_filler_tokens[:insertion_index]
        + needle_tokens
        + limited_filler_tokens[insertion_index:]
    )

    return tokenizer.decode(final_tokens)


def count_tokens(
    text: str,
    tokenizer: Tokenizer,
) -> int:
    """Count tokens using the configured tokenizer."""

    return tokenizer.count(text)
