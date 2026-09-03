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
