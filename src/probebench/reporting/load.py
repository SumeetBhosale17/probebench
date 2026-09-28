"""Read the archive as one table: migrate, flatten, join, aggregate.

This is build-order step 1's last missing piece. Everything upstream of it
exists - 590 records across six schema versions, content-addressed identity,
a migration chain - and none of it is usable for a claim until something reads
them together.

**The guards are the point, not the loading.** Reading JSONL is ten lines. What
this module adds is that the four ways this archive will silently mislead you
are RAISES rather than footnotes:

* Pooling experiments that are not comparable (LIMITATIONS 1.20). The three
  long-range families emit identical metric names over the same corpus at the
  same lengths and measure retrieval, discrimination and composition. Nothing
  in a record stops you averaging them.
* Treating an absent metric as a zero, or as a smaller denominator (1.7,
  invariant 1). A rate here always carries its `n` and its `n_absent`.
* Reporting a compliance rate over records that never stored the instruction
  (J-021). Obedience is a relation between a response and an instruction; no
  record before schema 1.4 has one, so the rate is undefined rather than low.
* Reporting a judge score from a self-judged run (1.2, J-006). qwen3:0.6b
  grading its own correct answers returned 0.0 with reasons that named the
  expected string in the clause calling it missing.

Each raises a distinct exception with the limitation in the message, and each
has a named escape hatch so that overriding it is visible at the call site
rather than a default nobody chose.

**One trap this module deliberately does NOT smooth over.** `coverage()` reports
both `lexical` and `lexical_exact_match` in `metrics_seen`. They are not
aliases - they are two of the three rule definitions that share two names in
this archive (D-014), and nothing in a record says which produced a given value.
Mapping one onto the other would pool incompatible definitions into a single
rate, which is the defect, not the fix. So a rate over `lexical_exact_match`
counts the `lexical` records as ABSENT and says so in `n_absent`. Check
`coverage()` before reading any rate, and treat a large `n_absent` as a question
rather than a rounding error.
"""

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from probebench.core.migrations import migrate_record
from probebench.core.schema import CURRENT_SCHEMA_VERSION

# Join keys. They answer different questions and a claim must say which it used
# (D-012). `case_fingerprint` asserts the model saw identical bytes and will
# CORRECTLY stop joining across models once LIMITATIONS 1.1 is fixed;
# `case_key` asserts the same design point and survives that fix, but then means
# "same nominal cell", not "same input".
STRICT_JOIN = "case_fingerprint"
DESIGN_JOIN = "case_key"


class PoolingError(ValueError):
    """Rows from experiments that are not comparable were aggregated."""


class UnreportableError(ValueError):
    """A metric exists but the records cannot support a claim about it."""


@dataclass(frozen=True)
class Row:
    """One case, flattened, with the whole record still reachable.

    The nested record is kept because the families differ in what their `case`
    block holds - `registry_rotation` and `target_rank` exist only for multi-hop,
    `distractor_count` only for the keyed family - and flattening to a fixed
    column set would silently drop exactly the fields the diagnostic work needs.
    """

    schema_version: str
    run_id: str
    benchmark: str
    experiment: str
    model: str
    case_id: str
    case_key: str | None
    case_fingerprint: str | None
    status: str
    expected: str
    predicted: str
    metrics: Mapping[str, float]
    case: Mapping[str, Any]
    record: Mapping[str, Any] = field(repr=False)

    def metric(self, name: str) -> float | None:
        """A metric, or None when it is ABSENT.

        Never 0.0 for a missing metric. Invariant 1 is enforced at write time;
        this is the read-side half of it, and the reason the return type is
        optional rather than defaulted.
        """

        value = self.metrics.get(name)

        return None if value is None else float(value)

    @property
    def source(self) -> str:
        """`run.experiment` scoped by family - the pooling unit (1.20)."""

        return f"{self.benchmark}/{self.experiment}"

    @property
    def judge_model(self) -> str | None:
        return self.record.get("evaluation", {}).get("judge", {}).get("model")

    @property
    def self_judged(self) -> bool:
        return self.judge_model is not None and self.judge_model == self.model


@dataclass(frozen=True)
class Rate:
    """A metric's mean, with everything needed to know whether to believe it.

    `n_absent` is carried rather than folded into the denominator because
    LIMITATIONS 1.7 is that absent metrics change denominators: a judge that
    errored on 30 of 100 cases gives a rate over 70, and a reader comparing it
    with a rate over 100 is comparing two different quantities.
    """

    metric: str
    value: float | None
    n: int
    n_absent: int
    n_error: int

    @property
    def coverage(self) -> float:
        total = self.n + self.n_absent

        return self.n / total if total else 0.0

    def __str__(self) -> str:
        if self.value is None:
            return f"{self.metric}: undefined (0 of {self.n_absent} scored)"

        suffix = f", {self.n_absent} absent" if self.n_absent else ""

        return f"{self.metric}: {self.value:.3f} (n={self.n}{suffix})"


def load_records(source: str | Path | Iterable[str | Path]) -> Iterator[dict[str, Any]]:
    """Every record under `source`, migrated to the current schema.

    Accepts a directory, a single file, or an iterable of either. Migration is
    unconditional: the archive holds six declared versions and at least three
    distinct shapes claiming "1.0" (J-005), so reading without migrating means
    reading whichever shape happened to be written that week.
    """

    for path in _resolve(source):
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue

                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{number} is not valid JSON: {exc}") from exc

                migrated = migrate_record(raw)

                if migrated["schema_version"] != CURRENT_SCHEMA_VERSION:
                    raise ValueError(
                        f"{path}:{number} migrated to {migrated['schema_version']}, "
                        f"expected {CURRENT_SCHEMA_VERSION}"
                    )

                yield migrated


def load_rows(source: str | Path | Iterable[str | Path]) -> list[Row]:
    """Every record as a Row."""

    return [_to_row(record) for record in load_records(source)]


def group_by(rows: Sequence[Row], *keys: str) -> dict[tuple[Any, ...], list[Row]]:
    """Bucket rows by case fields, dotted paths, or Row attributes.

    `group_by(rows, "experiment", "depth", "case.registry_size")` - a bare name
    is tried as a Row attribute first, then as a `case` field, so the common
    columns read naturally and the family-specific ones are still reachable.
    """

    buckets: dict[tuple[Any, ...], list[Row]] = {}

    for row in rows:
        bucket = tuple(_lookup(row, key) for key in keys)
        buckets.setdefault(bucket, []).append(row)

    return buckets


def rate(
    rows: Sequence[Row],
    metric: str,
    *,
    across_experiments: bool = False,
    allow_missing_instruction: bool = False,
    allow_self_judged: bool = False,
) -> Rate:
    """The mean of one metric, with the archive's four traps as errors.

    The keyword escapes exist so that a deliberate override appears at the call
    site. A default that silently permitted any of these would make the guard
    decorative - which is what a warning would be, since nobody reads warnings
    in a notebook.
    """

    if not rows:
        return Rate(metric=metric, value=None, n=0, n_absent=0, n_error=0)

    sources = {row.source for row in rows}

    if len(sources) > 1 and not across_experiments:
        raise PoolingError(
            f"Refusing to aggregate {metric!r} across {len(sources)} experiments: "
            f"{', '.join(sorted(sources))}. They emit the same metric names over the "
            "same corpus and measure different tasks - retrieval, discrimination and "
            "composition (LIMITATIONS 1.20). Group by experiment first, or pass "
            "across_experiments=True if the pooling is genuinely intended."
        )

    if metric == "instruction_compliance" and not allow_missing_instruction:
        blind = [row for row in rows if not row.case.get("system_prompt")]

        if blind:
            raise UnreportableError(
                f"{len(blind)} of {len(rows)} records have no `case.system_prompt`, so a "
                "compliance RATE is undefined for them: obedience is a relation between a "
                "response and an instruction, and no schema before 1.4 stored the "
                "instruction (J-021). The response-FORM rate is still available - pass "
                "allow_missing_instruction=True and report it as form, not obedience."
            )

    if metric == "llm_judge" and not allow_self_judged:
        judged = [row for row in rows if row.self_judged]

        if judged:
            raise UnreportableError(
                f"{len(judged)} of {len(rows)} records were SELF-JUDGED - the judge model "
                "is the generation model (LIMITATIONS 1.2, J-006). qwen3:0.6b grading its "
                "own correct answers returned 0.0 with reasons that named the expected "
                "string in the clause calling it missing. Pass allow_self_judged=True only "
                "to inspect, never to report."
            )

    scored = [row.metric(metric) for row in rows]
    present = [value for value in scored if value is not None]

    n_error = sum(1 for row in rows if row.status != "ok")

    return Rate(
        metric=metric,
        value=sum(present) / len(present) if present else None,
        n=len(present),
        n_absent=len(scored) - len(present),
        n_error=n_error,
    )


def aggregate(
    rows: Sequence[Row],
    metric: str,
    by: Sequence[str],
    **guards: bool,
) -> list[tuple[tuple[Any, ...], Rate]]:
    """`rate` per group, sorted by group key.

    Grouping by `experiment` is what makes the pooling guard pass, so the common
    correct usage needs no escape hatch.
    """

    grouped = group_by(rows, *by)

    return [(key, rate(grouped[key], metric, **guards)) for key in sorted(grouped, key=_sortable)]


def join(
    rows: Sequence[Row],
    on: str = STRICT_JOIN,
    *,
    require_distinct_models: bool = True,
) -> dict[str, dict[str, Row]]:
    """Index rows by join key, then by model - the cross-model comparison table.

    Returns only keys present for more than one model, because a key seen once
    contributes nothing to "do different models fail on the same inputs?" and
    padding the table with them makes the join look better than it is.
    """

    if on not in (STRICT_JOIN, DESIGN_JOIN):
        raise ValueError(f"Join key must be {STRICT_JOIN!r} or {DESIGN_JOIN!r}, got {on!r}")

    table: dict[str, dict[str, Row]] = {}

    for row in rows:
        key = row.case_fingerprint if on == STRICT_JOIN else row.case_key

        if not key:
            # Pre-1.2 records have no fingerprint and cannot get one - the
            # prompt was never stored and cannot be reconstructed. Absent, not
            # synthesised (invariant 8 applied to identity).
            continue

        table.setdefault(key, {})[row.model] = row

    if not require_distinct_models:
        return table

    return {key: models for key, models in table.items() if len(models) > 1}


def coverage(rows: Sequence[Row]) -> dict[str, Any]:
    """What the archive actually contains - run this before believing a figure."""

    joinable = sum(1 for row in rows if row.case_fingerprint)

    return {
        "records": len(rows),
        "runs": len({row.run_id for row in rows}),
        "experiments": sorted({row.source for row in rows}),
        "models": sorted({row.model for row in rows}),
        "schema_versions_after_migration": sorted({row.schema_version for row in rows}),
        "with_fingerprint": joinable,
        "without_fingerprint": len(rows) - joinable,
        "with_system_prompt": sum(1 for row in rows if row.case.get("system_prompt")),
        "self_judged": sum(1 for row in rows if row.self_judged),
        "non_ok_status": sum(1 for row in rows if row.status != "ok"),
        "metrics_seen": sorted({name for row in rows for name in row.metrics}),
    }


def _resolve(source: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(source, (str, Path)):
        path = Path(source)

        if path.is_dir():
            return sorted(path.glob("*.jsonl"))

        return [path]

    paths: list[Path] = []

    for item in source:
        paths.extend(_resolve(item))

    return paths


def _to_row(record: Mapping[str, Any]) -> Row:
    case = record.get("case", {})
    run = record.get("run", {})
    response = record.get("response", {})

    return Row(
        schema_version=record.get("schema_version", "unknown"),
        run_id=run.get("run_id", "unknown"),
        benchmark=run.get("benchmark", "unknown"),
        experiment=run.get("experiment", "unknown"),
        model=record.get("model", {}).get("name", "unknown"),
        case_id=case.get("case_id", "unknown"),
        case_key=case.get("case_key"),
        case_fingerprint=case.get("case_fingerprint"),
        status=response.get("status", "ok"),
        expected=response.get("expected", ""),
        predicted=response.get("predicted", ""),
        metrics=record.get("metrics", {}),
        case=case,
        record=record,
    )


def _lookup(row: Row, key: str) -> Any:
    if "." in key:
        head, _, tail = key.partition(".")
        target = getattr(row, head, None) if head != "case" else row.case

        return target.get(tail) if isinstance(target, Mapping) else None

    if hasattr(row, key):
        return getattr(row, key)

    return row.case.get(key)


def _sortable(key: tuple[Any, ...]) -> tuple[Any, ...]:
    """Sort group keys that mix None with numbers and strings."""

    return tuple(
        (value is None, str(type(value)), value if value is not None else "") for value in key
    )
