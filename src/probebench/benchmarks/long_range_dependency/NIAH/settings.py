"""Typed validation for NIAH's construction knobs.

Lives here, not in core/settings.py, because CLAUDE.md's scope rule is that
anything in core/ mentioning needles is in the wrong place. core/ carries these
through as an opaque `params` dict; this module is what makes a typo in one of
them an error rather than a silently ignored key.

EVERY field here changes the bytes the model sees, and is therefore already
covered by `prompt_sha256` (and, for the corpus, `filler_sha256`) in the
existing fingerprint component set - so adding these knobs needs no
FINGERPRINT_VERSION bump (D-012 sub-decision 2).

The defaults must reproduce NiahBenchmark's hardcoded values byte-for-byte, or
every case_fingerprint in the archive stops matching a fresh run of the same
cell. There is a test that asserts exactly that.
"""

from probebench.core.settings import StrictSection


class NiahParams(StrictSection):
    """NIAH case-construction parameters. All of these are MEASURED."""

    filler_path: str = "data/long_range_dependency/NIAH/filler_text.txt"
    needles_path: str = "data/long_range_dependency/NIAH/needles.txt"

    # Hardcoded as class attributes until now. LIMITATIONS 1.9 measured needle
    # wording at 19 points of accuracy, which makes the question's wording a
    # first-order variable rather than scaffolding.
    question: str = "What is the important secret mentioned in the text?"

    system_prompt: str = (
        "You are a precise extraction engine. "
        "Answer ONLY with the secret code found in the text. "
        "Do not add any explanation."
    )
