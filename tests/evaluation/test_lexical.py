import pytest

from probebench.core.case import BenchmarkCase
from probebench.evaluation.long_range_dependency.NIAH.lexical import LexicalEvaluator

EXPECTED = "ALPHA-9921-X"


def _score(predicted: str) -> float:
    case = BenchmarkCase(case_id="t", benchmark="NIAH", prompt="", expected=EXPECTED, metadata={})
    return LexicalEvaluator().evaluate(case, predicted).score


@pytest.mark.parametrize(
    "predicted",
    [
        "ALPHA-9921-X",
        "ALPHA-9921-X.",
        "The important secret mentioned in the text is ALPHA-9921-X.",
        "The important secret ... is the access code, which is ALPHA-9921-X.",
        # J-014: asserts the answer, THEN editorialises. The commentary is the
        # grounded label's territory, not this metric's.
        'The important secret is the secret ingredient "ALPHA-9921-X" which is '
        "not a real ingredient but a fictional one.",
    ],
)
def test_asserted_answers_score_one(predicted: str) -> None:
    assert _score(predicted) == 1.0


@pytest.mark.parametrize(
    "predicted",
    [
        # All observed verbatim in 2bfcd3f32b11 (J-013).
        'There is no important secret mentioned in the text. The code "ALPHA-9921-X" '
        "is likely a fictional or humorous identifier added by the extraction engine.",
        "There is no important secret mentioned in the text. The secret code "
        '"ALPHA-9921-X" is not a real secret, but rather a placeholder I inserted.',
        "There is no important secret mentioned in the text. The mention of "
        "ALPHA-9921-X is likely an error or a joke.",
        "There is no important secret mentioned in the text. The text only mentions "
        'a fictional product called "ALPHA-9921-X" as a joke or a placeholder.',
    ],
)
def test_repudiations_score_zero(predicted: str) -> None:
    assert _score(predicted) == 0.0


def test_a_wrong_code_scores_zero() -> None:
    assert _score("The secret code is BETA-1234-Y.") == 0.0


def test_an_empty_response_scores_zero() -> None:
    assert _score("") == 0.0
