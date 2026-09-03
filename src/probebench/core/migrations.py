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


MIGRATIONS: dict[
    tuple[str, str],
    Migration,
] = {
    ("1.0", "1.1"): _migrate_1_0_to_1_1,
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
