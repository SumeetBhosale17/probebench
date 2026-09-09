"""The haystack primitive, shared by every long-range-dependency experiment.

Lifted out of `NIAH/generator.py` when the keyed families arrived. Splicing k
blocks into a token-controlled filler body is a FAMILY-level capability, not a
NIAH one - NIAH_distractor and NIAH_multihop differ from NIAH in what they plant
and what they ask, not in how planting works.

`NIAH/generator.py` re-exports all of this, so the archive's import paths and
the byte-identity test keep working unchanged.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from probebench.core.case_identity import sha256_text
from probebench.core.tokenizer import Tokenizer

# How a planted block is written into the haystack. The marker is a MEASURED
# variable, not scaffolding: at depth 1.0 the model disputes it as an artifact
# (J-012), and two responses have echoed it back verbatim (J-027).
MARKED_TEMPLATE = "\n\n[IMPORTANT SECRET]: {text}\n\n"


@dataclass(frozen=True)
class EncodedFiller:
    """The filler corpus, encoded once, carried with its digest.

    `tokens` is a TUPLE because one body is shared by every case in a sweep and
    a mutation would be invisible until the fingerprints stopped joining. The
    digest travels with it because the two are a pair - `filler_sha256` is a
    fingerprint component, and a body/digest mismatch would content-address an
    input that was never built.
    """

    tokens: tuple[int, ...]
    sha256: str

    @classmethod
    def encode(cls, filler: str, tokenizer: Tokenizer) -> "EncodedFiller":
        return cls(tokens=tuple(tokenizer.encode(filler)), sha256=sha256_text(filler))


@dataclass(frozen=True)
class Block:
    """One thing to plant in a haystack, before it is placed."""

    block_id: str  # stable within a case: "target", "d0", "pointer"
    role: str  # target | distractor | pointer
    subject: str  # what the block is ABOUT; "" for the legacy needles
    value: str  # the code it carries; "" for a pointer
    text: str  # the exact sentence, before the marker wrap
    requested_depth: float


@dataclass(frozen=True)
class PlacedBlock:
    """Where a Block actually landed.

    `document_index` is not decoration. A returned distractor is at least three
    different failures - wrong subject, positional bias, or an unresolved
    pointer - and only ORDER separates the second from the first. A distractor
    returned uniformly across slots is discrimination; one always returned from
    slot 0 is primacy, and has nothing to do with discrimination.
    """

    block_id: str
    role: str
    subject: str
    value: str
    text: str
    requested_depth: float
    realised_depth: float
    document_index: int
    token_offset: int
    token_count: int


@dataclass(frozen=True)
class Haystack:
    """A built context plus the full inventory of what was planted in it."""

    text: str
    total_tokens: int
    filler_tokens_used: int
    blocks: tuple[PlacedBlock, ...]


def load_filler(path: str) -> str:
    """Load filler text from disk."""

    with open(
        path,
        encoding="utf-8",
    ) as file:
        return file.read()


def build_haystack(
    *,
    filler: EncodedFiller,
    blocks: Sequence[Block],
    target_tokens: int,
    tokenizer: Tokenizer,
    block_template: str = MARKED_TEMPLATE,
) -> Haystack:
    """Splice k blocks into a token-controlled filler body at k depths.

    DEPTHS ARE COMPUTED AGAINST THE ORIGINAL BODY, never the growing one. The
    independence of the depths is the lesser reason. The real one: it holds the
    filler CONTENT at each insertion site identical across every cell of the
    grid. LIMITATIONS 1.9 measured the filler as a semantic distractor, so
    which Tolstoy passage neighbours a needle is a first-order variable - depths
    against a growing body would slide every later site and change that
    neighbour as a side effect of k, confounding the distractor axis with the
    filler-neighbourhood axis.

    Blocks are assembled by SEGMENT rather than spliced in place, so the
    "inserting ascending invalidates later indices" problem does not arise:
    nothing is mutated, so no index can be invalidated.

    Byte-identity: for a single block this reduces to exactly
    `body[:idx] + block + body[idx:]` with `idx = int(len(body) * depth)` and
    `len(body) = target_tokens - len(block)`, which is what shipped. The
    property is asserted two ways in tests/benchmarks/test_haystack_identity.py
    - against an independent reference implementation over the grid, and
    against 166 archived fingerprints.
    """

    if not blocks:
        raise ValueError("build_haystack requires at least one block.")

    for block in blocks:
        if not 0.0 <= block.requested_depth <= 1.0:
            raise ValueError(f"Depth must be between 0 and 1, got {block.requested_depth}")

    encoded = [tokenizer.encode(block_template.format(text=block.text)) for block in blocks]

    # The budget accounts for EVERY block, not one. At k=1 this is identical to
    # the single-needle arithmetic it replaces.
    max_filler_tokens = target_tokens - sum(len(tokens) for tokens in encoded)

    if max_filler_tokens <= 0:
        raise ValueError("Target token count is too small for the needle.")

    body = filler.tokens[:max_filler_tokens]

    indices = [int(len(body) * block.requested_depth) for block in blocks]

    if len(set(indices)) != len(indices):
        # Deliberately NOT repaired. Dropping a colliding block varies k across
        # cells and confounds depth with difficulty; shifting one perturbs the
        # background in exactly the cells where the target is nearest a
        # distractor, which is where the signal is. Callers choose depths that
        # interleave with the target grid, which makes this unreachable.
        raise ValueError(
            f"Two blocks resolve to the same insertion index: {indices}. "
            "Choose distractor depths that interleave with the target grid."
        )

    order = sorted(range(len(blocks)), key=lambda i: indices[i])

    final: list[int] = []
    placed: list[PlacedBlock] = []
    cursor = 0

    for document_index, i in enumerate(order):
        final.extend(body[cursor : indices[i]])
        cursor = indices[i]

        token_offset = len(final)
        final.extend(encoded[i])

        placed.append(
            PlacedBlock(
                block_id=blocks[i].block_id,
                role=blocks[i].role,
                subject=blocks[i].subject,
                value=blocks[i].value,
                text=blocks[i].text,
                requested_depth=blocks[i].requested_depth,
                # Provisional: the denominator is not known until every block
                # is placed, because each one displaces the ones after it.
                realised_depth=0.0,
                document_index=document_index,
                token_offset=token_offset,
                token_count=len(encoded[i]),
            )
        )

    final.extend(body[cursor:])

    total = len(final)

    # Requested and realised differ even at k=1 - a 16-token block at depth 1.00
    # in a 4,000-token context realises at 0.9960 - and the gap grows with k.
    # Recording it makes "the background moved" a measurement rather than an
    # assumption.
    inventory = tuple(replace(block, realised_depth=block.token_offset / total) for block in placed)

    return Haystack(
        text=tokenizer.decode(final),
        total_tokens=total,
        filler_tokens_used=len(body),
        blocks=inventory,
    )
