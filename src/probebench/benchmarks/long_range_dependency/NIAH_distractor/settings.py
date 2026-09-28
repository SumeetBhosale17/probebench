"""Typed validation for the distractor family's construction knobs.

Same scope rule as NIAH's: core/ carries these through as an opaque dict, and
this module is what makes a typo an error rather than a silently ignored key.
Every field here changes the bytes the model sees.
"""

from probebench.core.settings import StrictSection

# Decoy positions, on SIXTEENTHS. Deliberately disjoint from the tenths the
# target sweeps, so a decoy can never land on the target's index and trip
# build_haystack's collision guard - which raises rather than repairing,
# because both repairs (shift, drop) corrupt the measurement.
BACKGROUND_DEPTHS: tuple[float, ...] = (
    0.0625,
    0.1875,
    0.3125,
    0.4375,
    0.5625,
    0.6875,
    0.8125,
    0.9375,
)


class NiahDistractorParams(StrictSection):
    """Keyed-needle discrimination parameters. All of these are MEASURED."""

    filler_path: str = "data/long_range_dependency/NIAH/filler_text.txt"
    needles_path: str = "data/long_range_dependency/NIAH_distractor/keyed_needles.jsonl"

    # k=0 is NOT a degenerate cell. It is D-023's calibration: NIAH's task and
    # structure with only the wording changed, which is the only thing that
    # turns the keyed-vs-legacy delta into a measured quantity instead of an
    # assumption. Dropping it would make every cross-arm figure unreportable.
    distractor_counts: tuple[int, ...] = (0, 1, 2, 4, 8)

    # Names the location rather than "the secret", because k+1 codes are present
    # and "the secret code" would not identify one. The question is a measured
    # variable (LIMITATIONS 1.9), so it is a knob, not a literal.
    system_prompt: str = (
        "You are a precise extraction engine. "
        "The text contains access codes for several different locations. "
        "Answer ONLY with the access code for the location named in the question. "
        "Do not add any explanation."
    )
