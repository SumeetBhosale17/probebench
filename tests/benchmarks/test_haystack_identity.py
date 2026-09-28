"""The constraint the whole archive rests on.

535 archived records join on `case_fingerprint`, which hashes `prompt_sha256`.
One changed byte in the single-needle haystack and every one of them stops
matching anything run afterwards.

These digests were captured from the implementation BEFORE the multi-insert
generalisation, so they are a genuine baseline rather than a re-derivation of
whatever the code happens to do now. A failure here means the refactor changed
the output, not that the expected values are stale - do not update them without
a DECISIONS entry saying why the archive is being abandoned.
"""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from probebench.benchmarks.long_range_dependency.NIAH.generator import (
    Block,
    EncodedFiller,
    build_haystack,
    create_haystack,
    extract_expected_answer,
    load_filler,
    load_needles,
)
from probebench.benchmarks.long_range_dependency.NIAH.identity import (
    build_case_fingerprint,
    build_case_key,
)
from probebench.benchmarks.long_range_dependency.NIAH.settings import NiahParams
from probebench.core.case_identity import sha256_text
from probebench.core.migrations import migrate_record
from probebench.tokenizers.tiktoken import TiktokenTokenizer

NEEDLE = "The secret access code is ALPHA-9921-X."
TARGET_TOKENS = 4_000

# depth -> (length in characters, sha256 prefix) of the produced haystack.
BASELINE = {
    0.0: (15_776, "d5289672ab695d117e8903d25e2df765"),
    0.5: (15_776, "3cb67bf4313aef6281c17317dcbbebb1"),
    1.0: (15_776, "2ca5b3a8cf429a20564bcddb0655633a"),
}


@pytest.fixture(scope="module")
def filler() -> str:
    return load_filler(NiahParams().filler_path)


@pytest.fixture(scope="module")
def tokenizer() -> TiktokenTokenizer:
    return TiktokenTokenizer("cl100k_base")


@pytest.mark.parametrize("depth", sorted(BASELINE))
def test_single_needle_haystack_is_byte_identical(
    depth: float,
    filler: str,
    tokenizer: TiktokenTokenizer,
) -> None:
    haystack = create_haystack(
        filler=filler,
        needle=NEEDLE,
        target_tokens=TARGET_TOKENS,
        depth=depth,
        tokenizer=tokenizer,
    )

    expected_length, expected_digest = BASELINE[depth]

    assert len(haystack) == expected_length
    assert hashlib.sha256(haystack.encode("utf-8")).hexdigest()[:32] == expected_digest


def test_the_needle_actually_appears(filler: str, tokenizer: TiktokenTokenizer) -> None:
    """A digest test alone would pass on a haystack that lost its needle."""

    haystack = create_haystack(
        filler=filler,
        needle=NEEDLE,
        target_tokens=TARGET_TOKENS,
        depth=0.5,
        tokenizer=tokenizer,
    )

    assert "ALPHA-9921-X" in haystack
    assert "[IMPORTANT SECRET]" in haystack


def test_depth_moves_the_needle(filler: str, tokenizer: TiktokenTokenizer) -> None:
    """Guards the ordering the digests cannot: 0.0 is early, 1.0 is late."""

    positions = {}

    for depth in (0.0, 0.5, 1.0):
        haystack = create_haystack(
            filler=filler,
            needle=NEEDLE,
            target_tokens=TARGET_TOKENS,
            depth=depth,
            tokenizer=tokenizer,
        )
        positions[depth] = haystack.index("ALPHA-9921-X") / len(haystack)

    assert positions[0.0] < positions[0.5] < positions[1.0]


# ---------------------------------------------------------------------------
# Leg 2: the archive replay.
#
# Stronger than the digests above, and free. A schema 1.4 `case` block stores
# needle, question, target_tokens, depth, filler_sha256, needle_template,
# tail_guard_tokens and system_prompt - everything build_case_fingerprint
# needs - so the haystack can be rebuilt and its content address re-derived end
# to end. This exercises the generator, the prompt assembly in
# _to_generic_case, identity.py and the component set at once, against values
# frozen on disk by the code as it was.
# ---------------------------------------------------------------------------

RAW_RESULTS = Path(__file__).resolve().parents[2] / "results" / "raw"

# Records that predate schema 1.2 have no fingerprint, and pre-1.4 records have
# no system prompt. Both are SKIPPED rather than half-checked: a partial
# component set would assert a match that was never computed.
MIN_REPLAYABLE_RECORDS = 166


def _archived_records() -> Iterator[dict]:
    for path in sorted(RAW_RESULTS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield migrate_record(json.loads(line))


@pytest.mark.skipif(not RAW_RESULTS.is_dir(), reason="no archived results present")
def test_every_archived_fingerprint_is_reproducible(
    filler: str,
    tokenizer: TiktokenTokenizer,
) -> None:
    checked = 0

    for record in _archived_records():
        case = record["case"]

        if not case.get("case_fingerprint") or not case.get("system_prompt"):
            continue

        # results/raw now holds more than one experiment. The keyed families
        # build their haystacks from a different inventory and address identity
        # with their own component sets, so replaying them through NIAH's
        # builder would compare two unrelated things. Their own construction is
        # covered by tests/benchmarks/test_keyed_families.py.
        if case.get("experiment") not in (None, "needle_in_a_haystack"):
            continue

        context = create_haystack(
            filler=filler,
            needle=case["needle"],
            target_tokens=case["target_tokens"],
            depth=case["depth"],
            tokenizer=tokenizer,
        )

        rebuilt = build_case_fingerprint(
            experiment=case["experiment"],
            prompt_sha256=sha256_text(f"{context}\n\nQuestion: {case['question']}"),
            system_prompt=case["system_prompt"],
            expected=record["response"]["expected"],
            needle=case["needle"],
            target_tokens=case["target_tokens"],
            depth=case["depth"],
            tokenizer_provider=record["tokenization"]["provider"],
            tokenizer_name=record["tokenization"]["name"],
            filler_sha256=case["filler_sha256"],
            needle_template=case["needle_template"],
            tail_guard_tokens=case["tail_guard_tokens"],
        )

        assert rebuilt == case["case_fingerprint"], case["case_id"]
        checked += 1

    # A test that silently checked zero records would pass forever.
    assert checked >= MIN_REPLAYABLE_RECORDS, f"only {checked} records were replayable"


def test_the_niah_case_key_is_frozen() -> None:
    """Pinned against a literal AND against the migration's independent copy.

    The pre-1.2 key format exists in two places - identity.py and
    _migrate_1_1_to_1_2 - written independently, with nothing asserting they
    agree. Adding an arm segment makes divergence likelier, so pin both.
    """

    key = build_case_key(
        target_tokens=4000,
        depth=0.5,
        needle=NEEDLE,
        needle_template="marked",
        tail_guard_tokens=0,
    )

    assert key == "niah/t4000/d0.50/n06bfb731/marked/g0"

    migrated = migrate_record(
        {
            "schema_version": "1.1",
            "case": {"needle": NEEDLE, "target_tokens": 4000, "depth": 0.5},
        }
    )

    assert migrated["case"]["case_key"] == key


# ---------------------------------------------------------------------------
# Leg 3: a differential test over the whole grid.
#
# The pinned digests above cover three points. This covers the (target x depth
# x needle) grid against an INDEPENDENT copy of the algorithm as it shipped.
# ---------------------------------------------------------------------------


def _reference_create_haystack(
    filler: str,
    needle: str,
    target_tokens: int,
    depth: float,
    tokenizer: TiktokenTokenizer,
) -> str:
    """The implementation as it shipped, copied verbatim.

    Deliberately NOT a call to `create_haystack`. That function now delegates to
    `build_haystack`, so comparing against it would be a tautology - the test
    would pass no matter what build_haystack did. An independent copy is the
    only version of this test that means anything after the collapse.
    """

    filler_tokens = tokenizer.encode(filler)
    needle_text = f"\n\n[IMPORTANT SECRET]: {needle}\n\n"
    needle_tokens = tokenizer.encode(needle_text)
    max_filler_tokens = target_tokens - len(needle_tokens)
    limited = filler_tokens[:max_filler_tokens]
    index = int(len(limited) * depth)

    return tokenizer.decode(limited[:index] + needle_tokens + limited[index:])


def test_one_block_matches_the_reference_over_the_grid(
    filler: str,
    tokenizer: TiktokenTokenizer,
) -> None:
    encoded = EncodedFiller.encode(filler, tokenizer)
    needles = load_needles(NiahParams().needles_path)

    for target_tokens in (1_000, 4_000, 8_000, 32_000):
        for depth in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
            for needle in needles:
                built = build_haystack(
                    filler=encoded,
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
                )

                assert built.text == _reference_create_haystack(
                    filler, needle, target_tokens, depth, tokenizer
                ), (target_tokens, depth, needle)


def test_multi_block_places_every_block_in_order(
    filler: str,
    tokenizer: TiktokenTokenizer,
) -> None:
    """k blocks land at distinct, ascending positions with realised depths."""

    blocks = [
        Block(
            block_id=f"d{i}",
            role="distractor",
            subject=f"site{i}",
            value=f"CODE-{i}",
            text=f"The code for site{i} is CODE-{i}.",
            requested_depth=depth,
        )
        for i, depth in enumerate((0.125, 0.375, 0.625, 0.875))
    ]
    blocks.append(
        Block(
            block_id="target",
            role="target",
            subject="vault",
            value="OMEGA-7732-Q",
            text="The code for the vault is OMEGA-7732-Q.",
            requested_depth=0.5,
        )
    )

    built = build_haystack(
        filler=EncodedFiller.encode(filler, tokenizer),
        blocks=blocks,
        target_tokens=4_000,
        tokenizer=tokenizer,
    )

    assert len(built.blocks) == 5
    assert [b.document_index for b in built.blocks] == [0, 1, 2, 3, 4]

    offsets = [b.token_offset for b in built.blocks]
    assert offsets == sorted(offsets)

    # Every planted value survives into the text, and realised depth tracks
    # requested depth without equalling it - the blocks displace each other.
    for block in built.blocks:
        assert block.value in built.text
        assert 0.0 <= block.realised_depth <= 1.0

    assert built.filler_tokens_used < 4_000


def test_colliding_depths_raise_rather_than_being_repaired(
    filler: str,
    tokenizer: TiktokenTokenizer,
) -> None:
    """Shifting perturbs the background exactly where the signal is; dropping
    varies k across cells. Neither is acceptable, so collision is an error."""

    same = [
        Block("a", "distractor", "x", "A-1", "The code for x is A-1.", 0.5),
        Block("b", "target", "y", "B-2", "The code for y is B-2.", 0.5),
    ]

    with pytest.raises(ValueError, match="same insertion index"):
        build_haystack(
            filler=EncodedFiller.encode(filler, tokenizer),
            blocks=same,
            target_tokens=4_000,
            tokenizer=tokenizer,
        )
