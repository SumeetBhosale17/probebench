import re

from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import (
    EvaluationResult,
    Evaluator,
    validate_score,
)

# Phrases in which a response quotes the expected answer in order to repudiate
# it: to deny the answer is present, or to call it fake, inserted, or a joke.
#
# Deliberately narrow (D-011). Matching hedges or general discussion of the
# text would turn false positives into false NEGATIVES, which is the worse
# error here - a false negative reads as a model failure and gets written up
# as one. Every pattern below is taken from an observed response in
# results/raw/long_range_dependency_NIAH_llama3_8b_2bfcd3f32b11.jsonl (J-013).
_REPUDIATION = re.compile(
    r"""
      there \s is \s no \s (?:\w+\s){0,3}? secret
    | no \s (?:specific|explicit|important|actual) \s (?:\w+\s){0,2}? secret
    | (?:does|do) \s not \s (?:contain|mention|reveal|include) \s
        (?:\w+\s){0,3}? (?:secret|code|password|key|identifier)
    | not \s a \s real \s (?:secret|code|password|key)
    | (?:is|as) \s (?:likely \s )? (?:a|an) \s
        (?:mistake|error|joke|placeholder|fictional|humorous)
    | (?:fictional|fake|placeholder|dummy|humorous) \s
        (?:secret|code|password|key|identifier|product|ingredient)
    | (?:inserted|added) \s by \s the \s (?:extraction \s engine|system)
    | placeholder \s i \s inserted
    """,
    re.IGNORECASE | re.VERBOSE,
)


class LexicalEvaluator(Evaluator):
    """Checks whether the response ASSERTS the expected answer.

    This remains binary because the benchmark is testing exact
    retrieval of a secret/code.

    Containment alone is not enough: a model that quotes the code while
    denying it is real satisfies `expected in response` and would score 1.0
    for a refusal. That happened 16 times in one 330-case run and overstated
    accuracy by five points (JOURNAL J-013, DECISIONS D-011), so containment
    is paired with a repudiation guard.
    """

    name = "lexical_exact_match"

    def evaluate(self, case: BenchmarkCase, predicted: str) -> EvaluationResult:

        expected = case.expected.strip().casefold()
        response = predicted.strip().casefold()

        contains = expected in response

        # The guard only ever REMOVES credit, so it cannot turn a genuine
        # failure into a pass - it can only be too strict, never too generous.
        score = 1.0 if contains and not _REPUDIATION.search(response) else 0.0

        return EvaluationResult(
            name=self.name,
            score=validate_score(score),
        )
