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


MIGRATIONS: dict[
    tuple[str, str],
    Migration,
] = {}


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
