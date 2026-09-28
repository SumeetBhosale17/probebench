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

    # How many cyclic rotations of the registry to sweep (D-024).
    #
    # Rotation r assigns the SAME k subjects to the depth slots starting at
    # offset r, so across k rotations every subject occupies every rank exactly
    # once - a Latin square, which makes rank and subject identity orthogonal by
    # construction. That is what J-032 could not do: its registry was file-order
    # only, so rank 2 was always Kingsley and its 80% failure rate had three
    # equally good explanations.
    #
    # Capped rather than always-k because a full square at k=8 is 8x the cases.
    # 4 rotations of an 8-registry still has every subject visiting 4 distinct
    # ranks, which separates the hypotheses; it just does not balance them.
    #
    # r=0 reproduces the pre-D-024 layout exactly, so the 50 archived multi-hop
    # records remain joinable and become the r=0 stratum rather than dead data.
    max_registry_rotations: int = 4

    system_prompt: str = (
        "You are a precise extraction engine. "
        "The text contains access codes for several different locations, and "
        "some locations share a code with another location. "
        "Answer ONLY with the access code for the location named in the question. "
        "Do not add any explanation."
    )
