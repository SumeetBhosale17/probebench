"""Did the response obey "answer ONLY with the code"? (D-018)

This measures the FORM of a response and deliberately never looks at the
expected answer's VALUE. Defining compliance as "the response equals the
expected string" would make it a strictly stronger `lexical_exact_match`:
every compliant response would be correct by construction, the "obeyed the
format but retrieved the wrong code" cell would be unreachable rather than
merely unobserved, and the retrieval x compliance composite would collapse
algebraically to its second term. J-022 confirms that cell is empty today
(0 of 424), so both definitions score the current archive identically - which
is exactly why the better-defined one costs nothing to adopt.

A caution the name cannot carry. The rule sees a response; obedience is a
relation between a response and an instruction, and no record at any schema
version stored the instruction before 1.4 (J-021). The guard lives in the
reporting layer, which must refuse a compliance RATE for records lacking
`case.system_prompt` - the response-form rate is always available, the
obedience reading is not.
"""

import re
import unicodedata

from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import (
    EvaluationResult,
    Evaluator,
    validate_score,
)

# Bumped whenever the normalisation below changes what it decides, and recorded
# on every result. This is the one thing `lexical_exact_match` cannot do: three
# definitions share two names in the archive and nothing says which produced a
# given value (D-014). This metric is born with that fixed.
RULE_VERSION = "1.0"

# Markdown emphasis and code fences carry no words. The instruction forbids
# explanation, not formatting, so stripping these is not leniency - it refuses
# to score a property the model was never told about.
_MARKUP = re.compile(r"[*_`~]+")

# Straight and typographic quotes, both directions.
_QUOTES = "\"'‘’“”«»"

# TRAILING sentence punctuation only. A LEADING full stop would mean the
# response began with something that is not the answer.
_TRAILING_PUNCTUATION = ".,;:!"

_WHITESPACE = re.compile(r"\s")

# Compliant under the LENIENT reading. The strict reading is "exact" alone;
# both stay recomputable from a stored record because the verdict is kept, not
# just the score. The band between them is 5 records in 424, all `CODE.`
# (J-022), so the choice of line barely matters - but a later reader should not
# have to take that on trust.
COMPLIANT_VERDICTS = frozenset({"exact", "stripped"})


def normalise_answer(text: str) -> str:
    """Reduce a response to the value it would be if nothing had been added."""

    stripped = unicodedata.normalize("NFKC", text).strip()

    stripped = _MARKUP.sub("", stripped).strip()

    # Quotes are stripped on BOTH sides of the punctuation pass because both
    # `"CODE."` and `"CODE".` occur, and one pass handles only one of them.
    stripped = stripped.strip(_QUOTES).strip()
    stripped = stripped.rstrip(_TRAILING_PUNCTUATION).strip()
    stripped = stripped.strip(_QUOTES).strip()

    return stripped


def classify_form(text: str) -> str:
    """Which SHAPE a response has: exact | stripped | prose | empty.

    Four verdicts rather than a bool so the strict reading ("exact" only) and
    the lenient one are both recoverable from a stored record without
    re-running this function.

    "One bare value" is decided by the ABSENCE OF WHITESPACE. That is sound for
    NIAH specifically - every expected answer is a single whitespace-free code,
    by construction in `extract_expected_answer`. A family whose answers
    contain spaces needs a different rule, which is why this module lives here
    and not in core/.
    """

    if not text.strip():
        return "empty"

    core = normalise_answer(text)

    # Reachable when a response is markup or punctuation only, e.g. "**".
    # Nothing survives that could be an answer, so it is the empty case.
    if not core:
        return "empty"

    if _WHITESPACE.search(core):
        return "prose"

    return "exact" if core == text.strip() else "stripped"


def is_answer_only(text: str) -> bool:
    """Whether the response is one bare value with no prose around it.

    An EMPTY response is NOT compliant. It adds no explanation, but it answers
    nothing, and scoring silence as obedience would put a pass on the one
    response shape that is unambiguously a failure.

    A free function, not only a method, because the rule tier must be
    replayable over stored JSONL without instantiating anything or calling a
    model (CLAUDE.md build-order step 4). Every archived record stores
    `response.predicted`, so every archived record can be scored offline.
    """

    return classify_form(text) in COMPLIANT_VERDICTS


class InstructionComplianceEvaluator(Evaluator):
    """Scores whether the response is the answer alone (D-018).

    Binary, like `lexical_exact_match`, and for the same reason: the question
    is "did it, yes or no", not "how much". Kept out of any stored composite -
    the conjunction with retrieval is composed by the reporting layer, never
    written to disk, because a stored composite would be a fourth rule
    definition depending on two inputs whose definitions have already moved
    twice (D-011, J-005, D-014).
    """

    name = "instruction_compliance"

    def evaluate(self, case: BenchmarkCase, predicted: str) -> EvaluationResult:

        expected = case.expected.strip()

        # The whitespace test is only meaningful when the answer space is
        # single-token. Raising leaves the metric ABSENT (invariant 1) rather
        # than scoring 0.0 on every case of a family this rule was never
        # designed for, where a silent 0.0 would look like total
        # non-compliance and would be written up as one.
        if not expected or _WHITESPACE.search(expected):
            raise ValueError(
                "instruction_compliance is undefined for a multi-token expected "
                f"answer: {expected!r}"
            )

        verdict = classify_form(predicted)

        return EvaluationResult(
            name=self.name,
            score=validate_score(1.0 if verdict in COMPLIANT_VERDICTS else 0.0),
            metadata={
                "rule_version": RULE_VERSION,
                # The evidence that makes the score auditable offline and the
                # strict/lenient band recomputable without re-running the rule
                # - the job `unsupported_claim` does for `grounded` (D-010).
                "verdict": verdict,
            },
        )
