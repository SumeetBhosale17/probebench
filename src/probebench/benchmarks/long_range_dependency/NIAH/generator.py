import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

def load_filler(path: str) -> str:
    """Load filler text from disk."""

    with open(path, encoding="utf-8") as file:
        return file.read()


def load_needles(path: str) -> list[str]:
    """Load non-empty needle line from disk."""

    with open(path, encoding="utf-8") as file:
        return [
            line.strip()
            for line in file
            if line.strip()
        ]

def extract_expected_answer(needle: str) -> str:
    """Extract the answer from existing needle format.
    
    Preserves the behavior of the original implementations:
    - If the needle contains quoted text, return quoted text.
    - Otherwise, if it contains 'is ', return the text after it.
    - Otherwise, use the complete needle.
    """

    if "'" in needle:
        parts = needle.split("'")

        if len(parts) >= 3:
            return parts[1].strip()

    if " is " in needle:
        answer = needle.split(" is ", maxsplit=1)[1]
        return answer.strip().rstrip(".")

    return needle.strip()

def create_haystack(
        filler: str,
        needle: str,
        target_tokens: int,
        depth: float,
) -> str:
    """Insert a needle at a token-based depth.
    
    depth=0.0 -> beginning
    depth=0.5 -> middle
    depth=1.0 -> end
    """

    if not 0.0 <= depth <= 1.0:
        raise ValueError(
            f"Depth must be between 0 and 1, got {depth}"
        )

    filler_tokens = enc.encode(filler)
    needle_text = f"\n\n[IMPORTANT SECRET]: {needle}\n\n"
    needle_tokens = enc.encode(needle_text)

    max_filler_tokens = target_tokens - len(needle_tokens)

    if max_filler_tokens <= 0:
        raise ValueError(
            f"Target token count ({target_tokens}) "
            "is too small for the needle."
        )

    limited_filler_tokens = filler_tokens[:max_filler_tokens]

    # Insert using token positions rather than character positions.
    insert_pos = int(len(limited_filler_tokens) * depth)

    final_tokens = (
        limited_filler_tokens[:insert_pos]
        + needle_tokens
        + limited_filler_tokens[insert_pos:]
    )

    return enc.decode(final_tokens)

def count_tokens(text: str) -> int:
    """Count tokens using the benchmark tokenizer."""

    return len(enc.encode(text))