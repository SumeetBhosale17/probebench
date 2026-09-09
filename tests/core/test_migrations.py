import json
from pathlib import Path

import pytest

from probebench.core.migrations import migrate_record
from probebench.core.schema import (
    CURRENT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    SchemaVersionError,
)

RAW_RESULTS = Path(__file__).resolve().parents[2] / "results" / "raw"


def test_current_version_is_supported() -> None:
    assert CURRENT_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS


def test_missing_version_raises() -> None:
    with pytest.raises(SchemaVersionError):
        migrate_record({})


def test_unknown_version_raises() -> None:
    with pytest.raises(SchemaVersionError):
        migrate_record({"schema_version": "0.9"})


def test_current_version_passes_through_unchanged() -> None:
    record = {"schema_version": CURRENT_SCHEMA_VERSION, "metrics": {"lexical": 1.0}}

    assert migrate_record(record) == record


def test_1_0_migrates_to_current() -> None:
    record = {"schema_version": "1.0", "metrics": {"lexical_exact_match": 1.0}}

    migrated = migrate_record(record)

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION

    # The input must not be mutated in place - a migration that edits its
    # argument corrupts the caller's copy of the archive.
    assert record["schema_version"] == "1.0"


def test_1_0_migration_does_not_synthesise_a_grounded_label() -> None:
    """Invariant 8: a run that predates the label has no label, not a clean one."""

    record = {
        "schema_version": "1.0",
        "evaluation_details": {"llm_judge": {"judge_model": "qwen3:4b"}},
    }

    migrated = migrate_record(record)

    assert "grounded" not in migrated["evaluation_details"]["llm_judge"]


@pytest.mark.skipif(not RAW_RESULTS.is_dir(), reason="no archived results present")
def test_every_archived_record_migrates() -> None:
    """The archive is the only real corpus this path has; it must all migrate.

    J-005 found three record shapes all declaring "1.0", so this is also the
    check that the migration does not assume a shape it cannot count on.
    """

    seen = 0

    for path in sorted(RAW_RESULTS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            migrated = migrate_record(json.loads(line))

            assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION

            seen += 1

    assert seen > 0


def test_1_0_migrates_all_the_way_to_current() -> None:
    """The chain walk, not just each hop (1.0 -> 1.1 -> 1.2)."""

    record = {
        "schema_version": "1.0",
        "case": {
            "needle": "The secret access code is ALPHA-9921-X.",
            "target_tokens": 4000,
            "depth": 0.5,
        },
    }

    migrated = migrate_record(record)

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert migrated["case"]["case_key"].startswith("niah/t4000/d0.50/n")

    # Never synthesised: the prompt was not stored, so there is nothing to
    # hash, and the machine is not recoverable from the record.
    assert migrated["case"]["case_fingerprint"] is None
    assert "host" not in migrated
    assert "done_reason" not in migrated.get("response", {})


def test_migrated_case_key_matches_a_freshly_built_one() -> None:
    """Archived and fresh keys must join, or case_key is pointless (D-015)."""

    from probebench.benchmarks.long_range_dependency.NIAH.identity import build_case_key

    needle = "The secret access code is ALPHA-9921-X."

    migrated = migrate_record(
        {
            "schema_version": "1.1",
            "case": {"needle": needle, "target_tokens": 4000, "depth": 0.5},
        }
    )

    assert migrated["case"]["case_key"] == build_case_key(
        target_tokens=4000,
        depth=0.5,
        needle=needle,
        needle_template="marked",
        tail_guard_tokens=0,
    )


def test_a_record_without_a_needle_still_migrates() -> None:
    """case_key is absent rather than fabricated when it cannot be derived."""

    migrated = migrate_record({"schema_version": "1.1", "case": {"case_id": "x"}})

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "case_key" not in migrated["case"]


def test_migrations_are_pure_functions_of_the_record() -> None:
    """No file I/O and no benchmark imports (D-015).

    A migration that read needles.txt would produce different keys depending
    on when it ran, so archived and fresh keys would silently stop joining.

    Checked over the parsed AST rather than the source text, because the
    comments explaining this rule necessarily mention the things it forbids.
    """

    import ast
    import inspect

    from probebench.core import migrations

    tree = ast.parse(inspect.getsource(migrations))

    imported: list[str] = []
    called: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.append(node.func.id)

    assert not [name for name in imported if "benchmarks" in name], imported
    assert "open" not in called


def test_1_2_to_1_3_does_not_backfill_a_measurement() -> None:
    """Invariant 8: an unverified run must not claim a measured precision.

    Every archived run set kv_cache_bytes_per_element from a flag that
    configured only the estimator (J-016), so copying it into the measured
    field would assert verification that never happened.
    """

    migrated = migrate_record(
        {
            "schema_version": "1.2",
            "generation": {"kv_cache_bytes_per_element": 2},
        }
    )

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "kv_cache_bytes_per_element_measured" not in migrated["generation"]
    assert "kv_cache_type_effective" not in migrated["generation"]

    # What the run ASKED for is derivable, and only that.
    assert migrated["generation"]["kv_cache_type_requested"] == "f16"


def test_1_2_to_1_3_reads_q8_0_from_the_byte_count() -> None:
    migrated = migrate_record(
        {"schema_version": "1.2", "generation": {"kv_cache_bytes_per_element": 1}}
    )

    assert migrated["generation"]["kv_cache_type_requested"] == "q8_0"


def test_1_3_to_1_4_does_not_synthesise_a_system_prompt() -> None:
    """The whole point of the field is that "never told" stays visible (J-021)."""

    migrated = migrate_record({"schema_version": "1.3", "case": {"case_id": "x"}})

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "system_prompt" not in migrated["case"]
    assert "system_prompt_sha256" not in migrated["case"]


def test_1_3_to_1_4_does_not_backfill_a_verdict() -> None:
    """A migration may compute an identity, never a rule's verdict (D-018).

    case_key was computed in 1.1 -> 1.2 because a key is definitionally stable.
    A rule's verdict is not: lexical_exact_match's guard was rewritten twice in
    one week. Baking one in would re-create J-005 using the tool built to cure
    it.
    """

    migrated = migrate_record(
        {
            "schema_version": "1.3",
            "metrics": {"lexical_exact_match": 1.0},
            "response": {"predicted": "ALPHA-9921-X", "expected": "ALPHA-9921-X"},
        }
    )

    assert "instruction_compliance" not in migrated["metrics"]


def test_stored_compliance_still_matches_the_current_rule() -> None:
    """Tripwire for the defect D-014 records but cannot repair.

    Vacuous today - no archived record carries the metric - and that is the
    point: it fires the first time the rule's definition drifts away from a
    value already written to disk, instead of letting two definitions pool
    silently under one key.
    """

    from probebench.evaluation.long_range_dependency.NIAH.compliance import is_answer_only

    for path in sorted(RAW_RESULTS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            record = migrate_record(json.loads(line))
            stored = record.get("metrics", {}).get("instruction_compliance")

            if stored is None:
                continue

            predicted = record.get("response", {}).get("predicted") or ""

            assert stored == (1.0 if is_answer_only(predicted) else 0.0), path.name


def test_1_4_to_1_5_does_not_reconstruct_an_inventory() -> None:
    """The tempting alternative, refused deliberately.

    NIAH's generator is deterministic, so an inventory for an archived record
    could be rebuilt exactly from needle/target_tokens/depth. Doing it here
    would make the migration depend on needles.txt and the 3.3 MB corpus - so
    the same record would migrate differently depending on when it ran, which
    is what test_migrations_are_pure_functions_of_the_record forbids.
    """

    record = {
        "schema_version": "1.4",
        "case": {
            "needle": "The secret access code is ALPHA-9921-X.",
            "target_tokens": 4000,
            "depth": 0.5,
            "system_prompt": "Answer ONLY with the secret code found in the text.",
        },
        "response": {"predicted": "ALPHA-9921-X", "expected": "ALPHA-9921-X"},
        "metrics": {"lexical_exact_match": 1.0},
    }

    migrated = migrate_record(record)

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION

    # Absent, not empty. An empty list would assert "nothing was planted",
    # which is false - one needle was, we just did not record where.
    for field in ("needle_inventory", "realised_depth", "filler_tokens_used"):
        assert field not in migrated["case"], field


def test_no_archived_record_gains_an_inventory() -> None:
    """Invariant 8 applied to construction: unrecorded is not empty."""

    if not RAW_RESULTS.is_dir():
        pytest.skip("no archived results present")

    checked = 0

    for path in sorted(RAW_RESULTS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            record = json.loads(line)

            # Records WRITTEN at 1.5 carry a real inventory - that is the whole
            # point of the version. The guard is about what a MIGRATION may
            # invent, so it applies only to records that predate the field.
            if record.get("schema_version") == "1.5":
                continue

            migrated = migrate_record(record)
            assert "needle_inventory" not in migrated.get("case", {}), path.name
            checked += 1

    assert checked > 0, "a test that checked zero records would pass forever"
