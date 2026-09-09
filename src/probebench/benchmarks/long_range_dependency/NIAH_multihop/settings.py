"""Typed validation for the multi-hop family's construction knobs.

Reuses the distractor family's keyed inventory: the same uniform template and
the same argument for it (D-022). What differs is that one extra block - the
pointer - makes the answer unreachable in a single lookup.
"""

from probebench.core.settings import StrictSection

# The pointer's own subject. Must NOT appear in keyed_needles.jsonl: if it did,
# the pointer would name a location that also has its own registry entry and the
# task would have two valid readings.
POINTER_SUBJECT = "Redmont"

POINTER_TEMPLATE = "The access code for {pointer} is the same as the access code for {target}."
POINTER_QUESTION = "What is the access code for {pointer}?"


class NiahMultihopParams(StrictSection):
    """Two-hop resolution parameters. All of these are MEASURED."""

    filler_path: str = "data/long_range_dependency/NIAH/filler_text.txt"
    needles_path: str = "data/long_range_dependency/NIAH_distractor/keyed_needles.jsonl"

    # Registry sizes. There is NO k=0 cell and no k=1 cell: with one entry the
    # only code in the text is the answer, so returning it proves nothing about
    # composing two hops. J-024's control found exactly this - the decoys are
    # the experiment, not the background.
    registry_sizes: tuple[int, ...] = (2, 4, 8)

    pointer_subject: str = POINTER_SUBJECT

    system_prompt: str = (
        "You are a precise extraction engine. "
        "The text contains access codes for several different locations, and "
        "some locations share a code with another location. "
        "Answer ONLY with the access code for the location named in the question. "
        "Do not add any explanation."
    )
