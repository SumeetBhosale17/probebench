import pytest

from probebench.core.case import BenchmarkCase
from probebench.evaluation.long_range_dependency.NIAH.compliance import (
    InstructionComplianceEvaluator,
    classify_form,
    is_answer_only,
)

EXPECTED = "ALPHA-9921-X"


def _score(predicted: str, expected: str = EXPECTED) -> float:
    case = BenchmarkCase(case_id="t", benchmark="NIAH", prompt="", expected=expected, metadata={})
    return InstructionComplianceEvaluator().evaluate(case, predicted).score


@pytest.mark.parametrize(
    ("predicted", "verdict"),
    [
        ("ALPHA-9921-X", "exact"),
        # Surrounding whitespace is not a modification of the answer, so this
        # is "exact" - only markup, quotes or punctuation make it "stripped".
        ("  ALPHA-9921-X  ", "exact"),
        ("ALPHA-9921-X.", "stripped"),
        ("**ALPHA-9921-X**", "stripped"),
        ('"ALPHA-9921-X"', "stripped"),
        ('"ALPHA-9921-X".', "stripped"),
        ("`ALPHA-9921-X`", "stripped"),
        # Observed verbatim in the archive.
        ("The important secret mentioned in the text is ALPHA-9921-X.", "prose"),
        ('The important secret mentioned in the text is:\n\n"ALPHA-9921-X"', "prose"),
        ("", "empty"),
        ("   ", "empty"),
        ("**", "empty"),
    ],
)
def test_verdicts(predicted: str, verdict: str) -> None:
    assert classify_form(predicted) == verdict


def test_a_bare_but_WRONG_answer_is_still_compliant() -> None:
    """The rule scores FORM, never the value (D-018, J-022).

    If this ever fails, compliance has become a stronger lexical_exact_match:
    the "obeyed the format, retrieved the wrong code" cell becomes unreachable
    by definition and the retrieval x compliance 2x2 collapses to one column.
    """

    assert _score("BETA-1234-Y") == 1.0


def test_an_empty_response_is_not_compliant() -> None:
    """Scoring silence as obedience would pass the one unambiguous failure."""

    assert _score("") == 0.0


def test_a_multi_token_expected_answer_raises() -> None:
    """Invariant 1: undefined leaves the metric ABSENT, it does not score 0.0."""

    with pytest.raises(ValueError):
        _score("two words", expected="two words")


def test_the_verdict_is_recorded_as_evidence() -> None:
    """The strict/lenient band must be recomputable without re-running the rule."""

    case = BenchmarkCase(case_id="t", benchmark="NIAH", prompt="", expected=EXPECTED, metadata={})
    result = InstructionComplianceEvaluator().evaluate(case, "ALPHA-9921-X.")

    assert result.metadata["verdict"] == "stripped"
    assert result.metadata["rule_version"]


def test_is_answer_only_agrees_with_classify_form() -> None:
    for text in ["X", "X.", "**X**", "a b", "", "**"]:
        assert is_answer_only(text) == (classify_form(text) in {"exact", "stripped"})
