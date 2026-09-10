"""The guards, not the loading.

Reading JSONL is ten lines and needs no test. What needs one is that the four
ways this archive misleads a reader are errors rather than footnotes - and,
just as importantly, that the escape hatches work, because a guard nobody can
get past gets deleted.
"""

import json
from pathlib import Path

import pytest

from probebench.core.schema import CURRENT_SCHEMA_VERSION
from probebench.reporting.load import (
    DESIGN_JOIN,
    STRICT_JOIN,
    PoolingError,
    Row,
    UnreportableError,
    aggregate,
    coverage,
    group_by,
    join,
    load_rows,
    rate,
)

RAW_RESULTS = Path(__file__).resolve().parents[2] / "results" / "raw"


def _row(
    *,
    experiment: str = "NIAH",
    model: str = "qwen3:4b",
    metrics: dict | None = None,
    system_prompt: str | None = "Answer ONLY with the code.",
    judge_model: str | None = None,
    fingerprint: str | None = "fp-1",
    case_key: str | None = "niah/t4000/d0.50",
    status: str = "ok",
    **case: object,
) -> Row:
    return Row(
        schema_version=CURRENT_SCHEMA_VERSION,
        run_id="r1",
        benchmark="long_range_dependency",
        experiment=experiment,
        model=model,
        case_id="c1",
        case_key=case_key,
        case_fingerprint=fingerprint,
        status=status,
        expected="ALPHA-9921-X",
        predicted="ALPHA-9921-X",
        metrics=metrics if metrics is not None else {"lexical_exact_match": 1.0},
        case={"system_prompt": system_prompt, **case},
        record={"evaluation": {"judge": {"model": judge_model}}},
    )


# ---------------------------------------------------------------------------
# Absent is not zero (invariant 1, LIMITATIONS 1.7)
# ---------------------------------------------------------------------------


def test_an_absent_metric_is_none_not_zero() -> None:
    assert _row(metrics={}).metric("lexical_exact_match") is None
    assert _row(metrics={"lexical_exact_match": 0.0}).metric("lexical_exact_match") == 0.0


def test_absent_metrics_leave_the_denominator_visible() -> None:
    """A judge that errored on 3 of 5 gives a rate over 2, and a reader
    comparing it with a rate over 5 is comparing two quantities (1.7)."""

    rows = [_row(metrics={"llm_judge": 1.0}), _row(metrics={"llm_judge": 0.0})]
    rows += [_row(metrics={}) for _ in range(3)]

    result = rate(rows, "llm_judge", allow_self_judged=True)

    assert result.value == 0.5
    assert result.n == 2
    assert result.n_absent == 3
    assert result.coverage == 0.4


def test_a_metric_absent_everywhere_is_undefined_not_zero() -> None:
    result = rate([_row(metrics={}) for _ in range(4)], "llm_judge", allow_self_judged=True)

    assert result.value is None
    assert result.n == 0
    assert "undefined" in str(result)


# ---------------------------------------------------------------------------
# The three refusals
# ---------------------------------------------------------------------------


def test_pooling_experiments_raises() -> None:
    """The three families emit the same metric names over the same corpus and
    measure different tasks (1.20). Nothing in a record stops you averaging."""

    rows = [_row(experiment="NIAH"), _row(experiment="NIAH_multihop")]

    with pytest.raises(PoolingError, match="across 2 experiments"):
        rate(rows, "lexical_exact_match")

    assert rate(rows, "lexical_exact_match", across_experiments=True).n == 2


def test_grouping_by_experiment_satisfies_the_pooling_guard() -> None:
    """The correct usage must not need an escape hatch, or the hatch becomes
    the default."""

    rows = [_row(experiment="NIAH"), _row(experiment="NIAH_multihop")]

    results = aggregate(rows, "lexical_exact_match", by=("experiment",))

    assert len(results) == 2
    assert all(r.n == 1 for _, r in results)


def test_compliance_without_a_stored_instruction_raises() -> None:
    """Obedience is a relation between a response and an instruction, and no
    schema before 1.4 stored the instruction (J-021)."""

    rows = [_row(metrics={"instruction_compliance": 1.0}, system_prompt=None)]

    with pytest.raises(UnreportableError, match="system_prompt"):
        rate(rows, "instruction_compliance")

    # The response-FORM rate is still available, and must be labelled as form.
    assert rate(rows, "instruction_compliance", allow_missing_instruction=True).value == 1.0


def test_self_judged_llm_judge_raises() -> None:
    """qwen3:0.6b grading its own correct answers returned 0.0 with reasons
    naming the expected string in the clause calling it missing (J-006)."""

    rows = [_row(metrics={"llm_judge": 1.0}, model="qwen3:4b", judge_model="qwen3:4b")]

    with pytest.raises(UnreportableError, match="SELF-JUDGED"):
        rate(rows, "llm_judge")

    assert rate(rows, "llm_judge", allow_self_judged=True).value == 1.0


def test_an_independent_judge_does_not_raise() -> None:
    rows = [_row(metrics={"llm_judge": 1.0}, model="qwen3:0.6b", judge_model="qwen3:4b")]

    assert rate(rows, "llm_judge").value == 1.0


# ---------------------------------------------------------------------------
# Joining
# ---------------------------------------------------------------------------


def test_join_keeps_only_keys_seen_by_more_than_one_model() -> None:
    """A key seen once contributes nothing to "do different models fail on the
    same inputs?" and padding the table makes the join look better than it is."""

    rows = [
        _row(model="qwen3:4b", fingerprint="fp-a"),
        _row(model="llama3:8b", fingerprint="fp-a"),
        _row(model="qwen3:4b", fingerprint="fp-b"),
    ]

    table = join(rows, on=STRICT_JOIN)

    assert set(table) == {"fp-a"}
    assert set(table["fp-a"]) == {"qwen3:4b", "llama3:8b"}
    assert set(join(rows, on=STRICT_JOIN, require_distinct_models=False)) == {"fp-a", "fp-b"}


def test_records_without_a_fingerprint_are_dropped_from_a_strict_join() -> None:
    """Pre-1.2 records cannot get one - the prompt was never stored and cannot
    be reconstructed. They still join on the design point."""

    rows = [
        _row(model="qwen3:4b", fingerprint=None, case_key="niah/t4000/d0.50"),
        _row(model="llama3:8b", fingerprint=None, case_key="niah/t4000/d0.50"),
    ]

    assert join(rows, on=STRICT_JOIN) == {}
    assert set(join(rows, on=DESIGN_JOIN)) == {"niah/t4000/d0.50"}


def test_an_unknown_join_key_raises() -> None:
    with pytest.raises(ValueError, match="Join key must be"):
        join([_row()], on="case_id")


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def test_group_by_reaches_row_attributes_and_case_fields() -> None:
    rows = [_row(depth=0.0), _row(depth=0.5), _row(depth=0.5)]

    assert {k: len(v) for k, v in group_by(rows, "depth").items()} == {(0.0,): 1, (0.5,): 2}
    assert list(group_by(rows, "case.depth")) == [(0.0,), (0.5,)]
    assert list(group_by(rows, "experiment")) == [("NIAH",)]


def test_group_keys_mixing_none_and_numbers_sort() -> None:
    """Family-specific fields are absent on other families, so a mixed column
    is normal rather than a defect."""

    rows = [_row(registry_size=4), _row(), _row(registry_size=2)]

    results = aggregate(rows, "lexical_exact_match", by=("registry_size",))

    assert len(results) == 3


# ---------------------------------------------------------------------------
# Against the real archive
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not RAW_RESULTS.is_dir(), reason="no archived results present")
def test_the_whole_archive_loads_as_one_shape() -> None:
    """The regression J-033 describes: 24 records had `model` as a bare string
    and every consumer written against the current layout broke on them."""

    rows = load_rows(RAW_RESULTS)

    assert len(rows) > 0
    assert {row.schema_version for row in rows} == {CURRENT_SCHEMA_VERSION}
    assert all(isinstance(row.model, str) and row.model != "unknown" for row in rows)


@pytest.mark.skipif(not RAW_RESULTS.is_dir(), reason="no archived results present")
def test_coverage_reports_what_is_actually_there() -> None:
    report = coverage(load_rows(RAW_RESULTS))

    assert report["records"] > 0
    assert report["schema_versions_after_migration"] == [CURRENT_SCHEMA_VERSION]

    # Both lexical names are present and are NOT aliased (D-014).
    assert "lexical_exact_match" in report["metrics_seen"]


def test_malformed_json_names_the_file_and_line(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text(json.dumps({"schema_version": "1.6"}) + "\n{ not json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="broken.jsonl:2"):
        load_rows(path)
