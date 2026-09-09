"""What the keyed families rest on, asserted rather than assumed.

D-022 adopted a uniform needle template to delete the 19-point wording confound
LIMITATIONS 1.9 measured. "Uniform" is a property of a data file, and a data
file drifts, so it is tested rather than trusted.
"""

import re

import pytest

from probebench.benchmarks.long_range_dependency.haystack import load_filler
from probebench.benchmarks.long_range_dependency.NIAH_distractor.benchmark import (
    NiahDistractorBenchmark,
    select_background_depths,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.needles import (
    NEEDLE_TEMPLATE,
    load_keyed_needles,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.settings import (
    BACKGROUND_DEPTHS,
    NiahDistractorParams,
)
from probebench.benchmarks.long_range_dependency.NIAH_multihop.benchmark import (
    NiahMultihopBenchmark,
)
from probebench.benchmarks.long_range_dependency.NIAH_multihop.settings import (
    NiahMultihopParams,
)
from probebench.tokenizers.tiktoken import TiktokenTokenizer


@pytest.fixture(scope="module")
def tokenizer() -> TiktokenTokenizer:
    return TiktokenTokenizer("cl100k_base")


@pytest.fixture(scope="module")
def needles():
    return load_keyed_needles(NiahDistractorParams().needles_path)


def test_every_keyed_needle_costs_the_same_number_of_tokens(needles, tokenizer) -> None:
    """The confound D-022 exists to delete, in its most literal form.

    A needle that is one token longer displaces one more filler token and sits
    at a fractionally different realised depth. That is small, but "small" is
    how the 19-point wording effect was described before it was measured.
    """

    costs = {len(tokenizer.encode(n.text)) for n in needles}

    assert len(costs) == 1, f"needles have {len(costs)} distinct token costs: {sorted(costs)}"


def test_every_keyed_value_has_the_same_shape(needles) -> None:
    shapes = {re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", n.value)) for n in needles}

    assert shapes == {"AAA-9999-AA"}


def test_keyed_values_and_subjects_are_distinct(needles) -> None:
    assert len({n.value for n in needles}) == len(needles)
    assert len({n.subject for n in needles}) == len(needles)

    # Distinct leading characters, so a partial-credit rule can never be
    # ambiguous about which planted code a prefix came from.
    assert len({n.value[0] for n in needles}) == len(needles)


def test_no_keyed_value_or_subject_occurs_in_the_filler(needles) -> None:
    """Otherwise the model could answer from the background, not from a block."""

    filler = load_filler(NiahDistractorParams().filler_path).lower()

    for needle in needles:
        assert needle.value.lower() not in filler, needle.value
        assert needle.subject.lower() not in filler, needle.subject


def test_the_needle_template_is_the_only_thing_that_varies(needles) -> None:
    for needle in needles:
        assert needle.text == NEEDLE_TEMPLATE.format(subject=needle.subject, value=needle.value)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def test_background_depths_cannot_collide_with_a_target_depth() -> None:
    """Why the background is on sixteenths while the target sweeps tenths.

    `build_haystack` RAISES on a collision rather than repairing one, because
    both repairs corrupt the measurement. This is the invariant that keeps that
    branch unreachable for every documented grid.
    """

    tenths = {round(i / 10, 4) for i in range(11)}

    assert not (set(BACKGROUND_DEPTHS) & tenths)


@pytest.mark.parametrize("k", [1, 2, 4, 8])
def test_decoys_spread_over_the_slots_rather_than_bunching(k: int) -> None:
    """Taking the first k would confound decoy COUNT with decoy POSITION."""

    depths = select_background_depths(k)

    assert len(depths) == k
    assert len(set(depths)) == k
    assert depths == sorted(depths)
    assert set(depths) <= set(BACKGROUND_DEPTHS)

    if k > 1:
        # Spread across the range, not clustered at one end.
        assert depths[0] < 0.5 < depths[-1]


def test_zero_decoys_is_a_valid_cell() -> None:
    """D-023's calibration. Not a degenerate case to be special-cased away."""

    assert select_background_depths(0) == []


def test_more_decoys_than_slots_raises() -> None:
    with pytest.raises(ValueError, match="only 8 background slots"):
        select_background_depths(9)


# ---------------------------------------------------------------------------
# The inventory, which is the reason both families exist
# ---------------------------------------------------------------------------


def _distractor_cases(tokenizer, **overrides):
    params = NiahDistractorParams()

    benchmark = NiahDistractorBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        system_prompt=params.system_prompt,
        distractor_counts=overrides.pop("distractor_counts", (0, 1, 2, 4, 8)),
        tokenizer=tokenizer,
        target_tokens=overrides.pop("target_tokens", [4_000]),
        depths=overrides.pop("depths", [0.5]),
        needles_per_configuration=overrides.pop("needles_per_configuration", 1),
        tokenizer_provider="tiktoken",
        tokenizer_name="cl100k_base",
        **overrides,
    )

    return benchmark.cases_as_generic()


def test_every_planted_value_reaches_the_prompt(tokenizer) -> None:
    for case in _distractor_cases(tokenizer):
        inventory = case.metadata["needle_inventory"]

        assert len(inventory) == case.metadata["distractor_count"] + 1

        for block in inventory:
            assert block["value"] in case.prompt, block


def test_exactly_one_block_is_the_target(tokenizer) -> None:
    for case in _distractor_cases(tokenizer):
        roles = [block["role"] for block in case.metadata["needle_inventory"]]

        assert roles.count("target") == 1
        assert roles.count("distractor") == case.metadata["distractor_count"]


def test_blocks_are_recorded_in_document_order(tokenizer) -> None:
    """`document_index` is what separates a positional bias from a
    discrimination failure, so it has to mean what it says."""

    for case in _distractor_cases(tokenizer):
        inventory = case.metadata["needle_inventory"]

        assert [b["document_index"] for b in inventory] == list(range(len(inventory)))
        assert [b["token_offset"] for b in inventory] == sorted(
            b["token_offset"] for b in inventory
        )

        positions = [case.prompt.index(b["value"]) for b in inventory if b["value"]]
        assert positions == sorted(positions)


def test_changing_a_decoy_changes_the_fingerprint(tokenizer) -> None:
    """D-012 pre-registered `distractors` three schema versions ago for this.

    If the component were ignored, two cases with the same target and different
    decoys would content-address identically - and the archive would silently
    pool the two design points the experiment exists to separate.
    """

    by_k = {
        case.metadata["distractor_count"]: case.metadata["case_fingerprint"]
        for case in _distractor_cases(tokenizer)
    }

    assert len(set(by_k.values())) == len(by_k), "fingerprints collide across k"


def test_case_keys_are_distinct_across_the_grid(tokenizer) -> None:
    cases = _distractor_cases(
        tokenizer,
        depths=[0.1, 0.5, 0.9],
        needles_per_configuration=3,
    )

    keys = [case.metadata["case_key"] for case in cases]

    assert len(set(keys)) == len(keys)


def test_a_distractor_case_never_joins_a_niah_case(tokenizer) -> None:
    """`experiment` is a fingerprint component, so k=0 - which is otherwise
    structurally a single-needle case - still cannot collide with NIAH."""

    for case in _distractor_cases(tokenizer, distractor_counts=(0,)):
        assert case.metadata["case_key"].startswith("niahd/")
        assert case.metadata["experiment"] == "needle_in_a_haystack_distractor"


# ---------------------------------------------------------------------------
# Multi-hop
# ---------------------------------------------------------------------------


def _multihop_cases(tokenizer, **overrides):
    params = NiahMultihopParams()

    benchmark = NiahMultihopBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        registry_sizes=overrides.pop("registry_sizes", (2, 4, 8)),
        pointer_subject=params.pointer_subject,
        system_prompt=params.system_prompt,
        tokenizer=tokenizer,
        target_tokens=overrides.pop("target_tokens", [4_000]),
        depths=overrides.pop("depths", [0.5]),
        needles_per_configuration=overrides.pop("needles_per_configuration", 2),
        tokenizer_provider="tiktoken",
        tokenizer_name="cl100k_base",
        **overrides,
    )

    return benchmark.cases_as_generic()


def test_the_pointer_never_carries_the_answer(tokenizer) -> None:
    """The one property that makes this a two-hop task at all.

    If the pointer block contained the code, a single-hop reader would score
    1.0 and the family would measure nothing NIAH does not.
    """

    for case in _multihop_cases(tokenizer):
        pointer = next(b for b in case.metadata["needle_inventory"] if b["role"] == "pointer")

        assert pointer["value"] == ""
        assert case.expected not in pointer["text"]


def test_the_answer_is_present_exactly_once_in_the_registry(tokenizer) -> None:
    for case in _multihop_cases(tokenizer):
        inventory = case.metadata["needle_inventory"]

        targets = [b for b in inventory if b["role"] == "target"]

        assert len(targets) == 1
        assert targets[0]["value"] == case.expected
        assert case.expected in case.prompt


def test_the_answer_slot_moves_across_the_sweep(tokenizer) -> None:
    """Without this, a registry positional bias would be invisible - every
    answer would sit in the same slot and the effect would look like a
    property of the task."""

    cases = _multihop_cases(tokenizer, registry_sizes=(4,), needles_per_configuration=4)

    slots = {
        next(b["document_index"] for b in c.metadata["needle_inventory"] if b["role"] == "target")
        for c in cases
    }

    assert len(slots) > 1, f"the answer always landed in slot {slots}"


def test_a_pointer_subject_with_its_own_entry_raises(tokenizer) -> None:
    """Two valid readings of the question is not a thing to warn about."""

    params = NiahMultihopParams()

    benchmark = NiahMultihopBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        registry_sizes=(4,),
        # A subject that DOES have a registry entry.
        pointer_subject="Brightwater",
        system_prompt=params.system_prompt,
        tokenizer=tokenizer,
        target_tokens=[4_000],
        depths=[0.5],
    )

    with pytest.raises(ValueError, match="also has a registry entry"):
        benchmark.cases_as_generic()
