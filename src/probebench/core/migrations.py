import hashlib
from collections.abc import Callable
from typing import Any

from probebench.core.schema import (
    CURRENT_SCHEMA_VERSION,
    SchemaVersionError,
)

Migration = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


def _migrate_1_0_to_1_1(
    record: dict[str, Any],
) -> dict[str, Any]:
    """1.1 adds the judge's groundedness label (D-010).

    The payload is deliberately left untouched. A 1.0 record was produced by a
    judge that was never asked about groundedness, so the honest value is
    ABSENT, not `null` and certainly not `true` - see invariant 8. Only the
    declared version moves, which is what lets a reader tell "this run predates
    the label" from "this run's judge failed", using the run's judge
    provenance rather than the field itself.

    Note the archive contains at least three record shapes all declaring "1.0"
    (JOURNAL J-005), so a reader must still detect shape by field presence.
    This migration does not repay that debt; it only stops adding to it.
    """

    migrated = dict(record)

    migrated["schema_version"] = "1.1"

    return migrated


# Constants that were implicit in every pre-1.2 run. Recording them makes a
# migrated record self-describing: case_key can be recomputed from the record
# alone, which is the property that lets archived and fresh keys join.
_PRE_1_2_NEEDLE_TEMPLATE = "marked"
_PRE_1_2_TAIL_GUARD_TOKENS = 0


def _migrate_1_1_to_1_2(
    record: dict[str, Any],
) -> dict[str, Any]:
    """1.2 adds case identity, evidence capture and host provenance (D-012).

    Three deliberate omissions, all of them invariant 8:

    * `case_fingerprint` is None. The prompt was never stored and cannot be
      reconstructed, so there is nothing honest to hash. Those records join on
      case_key only.
    * The `response` evidence fields (done_reason, prompt_eval_count, ...) are
      left ABSENT. The model was never asked, and a synthesised "stop" would
      assert that nothing was truncated.
    * `host` is left ABSENT. The machine is not recoverable from the record.

    `case_key` IS derivable, because every archived shape stores the needle
    text, target_tokens and depth. It is computed inline rather than imported
    from `benchmarks/` so this stays a pure function of the record with no file
    I/O (D-015) - a migration that read needles.txt would produce different
    keys depending on when it ran.
    """

    migrated = dict(record)
    migrated["schema_version"] = "1.2"

    case = dict(migrated.get("case", {}))

    needle = case.get("needle")
    target_tokens = case.get("target_tokens")
    depth = case.get("depth")

    if needle is not None and target_tokens is not None and depth is not None:
        needle_digest = hashlib.sha256(str(needle).encode("utf-8")).hexdigest()[:8]

        case["case_key"] = (
            f"niah/t{target_tokens}/d{float(depth):.2f}/n{needle_digest}"
            f"/{_PRE_1_2_NEEDLE_TEMPLATE}/g{_PRE_1_2_TAIL_GUARD_TOKENS}"
        )

    case["case_fingerprint"] = None
    case.setdefault("needle_template", _PRE_1_2_NEEDLE_TEMPLATE)
    case.setdefault("tail_guard_tokens", _PRE_1_2_TAIL_GUARD_TOKENS)

    migrated["case"] = case

    return migrated


def _migrate_1_2_to_1_3(
    record: dict[str, Any],
) -> dict[str, Any]:
    """1.3 records the MEASURED KV cache precision, not just the assumed one (D-017).

    `generation.kv_cache_bytes_per_element` already existed and keeps its
    meaning: what the memory estimator assumed. What it never meant - despite
    reading like it did - is what the server actually ran (J-016).

    The measured fields are left ABSENT rather than backfilled from the assumed
    one. Copying the assumption into the measurement would assert that every
    archived run was verified, when in fact none were and the flag that set it
    configured nothing. Invariant 8: unmeasured is missing data, not a value.
    """

    migrated = dict(record)
    migrated["schema_version"] = "1.3"

    generation = dict(migrated.get("generation", {}))

    # The one thing that IS derivable: what the run asked for. Pre-1.3 records
    # only stored the byte count, and it was always one of two values.
    assumed = generation.get("kv_cache_bytes_per_element")

    if assumed is not None and "kv_cache_type_requested" not in generation:
        generation["kv_cache_type_requested"] = "q8_0" if assumed == 1 else "f16"

    migrated["generation"] = generation

    return migrated


def _migrate_1_3_to_1_4(
    record: dict[str, Any],
) -> dict[str, Any]:
    """1.4 records the system prompt and adds metrics.instruction_compliance (D-018).

    Both are left ABSENT, for two different reasons worth keeping apart.

    `case.system_prompt` is absent because it is NOT RECOVERABLE. The string
    held the same value as a class attribute throughout, but it became
    configurable in D-016 and several archived runs came from machines this
    project does not control (D-013). Filling in today's default would assert
    that llama3:8b was given the instruction it appears to disobey - precisely
    the claim J-021 says the archive cannot support. Absent is what keeps
    "never obeyed" and "never told" distinguishable, which is the entire
    purpose of the field.

    `metrics.instruction_compliance` is absent because **a migration may
    compute an identity, never a verdict**. `case_key` was computed in
    1.1 -> 1.2 because a key is definitionally stable and versioned by
    FINGERPRINT_VERSION. A rule's verdict is not: the repudiation guard inside
    `lexical_exact_match` was rewritten twice inside one week (D-011, J-014). A
    migration that baked in a verdict would silently rewrite archived history
    every time the rule moved - J-005's three-definitions disease, reintroduced
    by the tool built to cure it.

    The archive is not lost for this metric, unlike `grounded` (needs a judge
    that never ran) or `case_fingerprint` (needs a prompt never stored):
    instruction_compliance is a pure function of `response.predicted`, which
    every archived shape carries, so it is REPLAYED at analysis time and
    stamped with the rule version actually applied.
    """

    migrated = dict(record)

    migrated["schema_version"] = "1.4"

    return migrated


def _migrate_1_4_to_1_5(
    record: dict[str, Any],
) -> dict[str, Any]:
    """1.5 records the needle inventory: what was planted, where, and as what.

    `case.needle_inventory` is a list of placed blocks, each with `block_id`,
    `role`, `subject`, `value`, `text`, `requested_depth`, `realised_depth`,
    `document_index`, `token_offset` and `token_count`. Alongside it,
    `case.realised_depth` and `case.filler_tokens_used`.

    Nothing in `to_record()` changed to produce this - `case_metadata` is
    splatted, so the shape moved while the function did not. That is exactly the
    drift J-005 found (three record shapes all declaring "1.0"), so the version
    tracks the SHAPE, not the source line that emits it.

    ALL THREE FIELDS ARE LEFT ABSENT on archived records, and the reason is
    worth stating because the alternative is tempting. NIAH's generator is
    deterministic, so an inventory for an archived 1.4 record could be
    reconstructed exactly from `needle`, `target_tokens` and `depth`. It is not,
    for two reasons: a migration is a pure function of the record (enforced by
    test - D-015), and reconstructing one would require reading needles.txt and
    the 3.3 MB corpus, so the same record would migrate differently depending on
    when it ran. Absent is honest; invariant 8 applied to construction rather
    than to labels.

    A reader wanting inventories for archived cases should REBUILD them at
    analysis time, where the corpus version is an explicit input rather than
    whatever happened to be on disk.
    """

    migrated = dict(record)

    migrated["schema_version"] = "1.5"

    return migrated


MIGRATIONS: dict[
    tuple[str, str],
    Migration,
] = {
    ("1.0", "1.1"): _migrate_1_0_to_1_1,
    ("1.1", "1.2"): _migrate_1_1_to_1_2,
    ("1.2", "1.3"): _migrate_1_2_to_1_3,
    ("1.3", "1.4"): _migrate_1_3_to_1_4,
    ("1.4", "1.5"): _migrate_1_4_to_1_5,
}


def migrate_record(
    record: dict[str, Any],
) -> dict[str, Any]:

    version = record.get("schema_version")

    if version is None:
        raise SchemaVersionError("Result is missing schema_version.")

    if version == CURRENT_SCHEMA_VERSION:
        return record

    current = record

    while current["schema_version"] != CURRENT_SCHEMA_VERSION:
        current_version = current["schema_version"]

        next_version = find_next_version(current_version)

        if next_version is None:
            raise SchemaVersionError(
                f"No migration path from {current_version} to {CURRENT_SCHEMA_VERSION}"
            )

        migration = MIGRATIONS[
            (
                current_version,
                next_version,
            )
        ]

        current = migration(current)

    return current


def find_next_version(
    version: str,
) -> str | None:

    for (
        source,
        target,
    ) in MIGRATIONS:
        if source == version:
            return target

    return None
