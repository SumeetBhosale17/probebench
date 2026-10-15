from probebench.core.settings import StrictSection

DEFAULT_ABSTAIN_TOKEN = "NO_EVIDENCE_FOUND"
BACKGROUND_DEPTHS = (
    0.0625,
    0.1875,
    0.3125,
    0.4375,
    0.5625,
    0.6875,
    0.8125,
    0.9375,
)


class NegativeRetrievalParams(StrictSection):
    """Synthetic answerability benchmark: retrieval versus abstention."""

    filler_path: str = "data/long_context_understanding/negative_retrieval/filler_text.txt"
    entity_path: str = "data/long_context_understanding/negative_retrieval/entities.jsonl"

    target_tokens: tuple[int, ...] = (4_000, 8_000, 16_000, 32_000)
    depths: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)
    entity_counts: tuple[int, ...] = (4, 8)

    answer_contract: str = (
        "Return exactly one string and nothing else: the exact value from the "
        "supplied text if it is present; otherwise return exactly "
        "NO_EVIDENCE_FOUND. No markdown, no quotes, no punctuation, no extra "
        "words, and no explanation."
    )

    system_prompt: str = (
        "You are an evidence-grounded extractor. Return exactly one string and "
        "nothing else. If the supplied text states the value, return the exact "
        "value verbatim. If the text does not state the requested value, return "
        "exactly NO_EVIDENCE_FOUND. No markdown, no quotes, no punctuation, no "
        "explanation, and no extra words."
    )
