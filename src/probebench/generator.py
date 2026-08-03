import tiktoken

enc = tiktoken.get_encoding("cl100k_base")


def load_filler(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_needles(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def create_haystack(filler: str, needle: str, target_tokens: int, depth: float) -> str:
    """Insert needle at a specific depth (0.0=start, 1.0=end)."""
    tokens = enc.encode(filler)

    needle_tokens = enc.encode(f"\n\n[IMPORTANT SECRET]: {needle}\n\n")
    needle_len = len(needle_tokens)

    max_filler_tokens = target_tokens - needle_len

    if max_filler_tokens <= 0:
        raise ValueError(f"Target tokens ({target_tokens}) is too small for the needle.")

    limited_tokens = tokens[:max_filler_tokens]

    base_text = enc.decode(limited_tokens)

    insert_pos = int(len(base_text) * depth)

    final_text = base_text[:insert_pos] + f"\n\n[IMPORTANT SECRET]: {needle}\n\n" + base_text[insert_pos:]
    return final_text


def count_tokens(text: str) -> int:
    return len(enc.encode(text))
