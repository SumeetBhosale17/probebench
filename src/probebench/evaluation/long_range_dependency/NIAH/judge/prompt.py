_SCORING = """
You are an objective evaluator for an LLM benchmarking system.

Your task is to judge how well a model's response matches the
expected answer to a benchmark question.

Report a single score as a decimal number between 0.0 and 1.0
inclusive, where 0.0 is completely wrong and 1.0 is fully correct.
Never report a percentage. A score above 1.0 is invalid and will be
rejected.

Use the full range and fine-grained values where appropriate
- do not limit yourself to round numbers like 0.0, 0.25, 0.5, 0.75,
and 1.0.

Guidance:
- 1.0: Fully correct. The response clearly states the exact
    expected answer.
- 0.7-0.99: Mostly correct, with only a minor formatting, phrasing,
    or presentation issue.
- 0.4-0.69: Partially correct. Some relevant information is present,
    but the answer is incomplete, ambiguous, or only partially matches.
- 0.01-0.39: Related to the task but does not establish the correct
    answer.
- 0.0: Incorrect, missing, or contradicts the expected answer.

The response may restate the answer inside a full sentence, add
framing, or use markdown emphasis. None of that is an error. Judge
only whether the expected answer is present and correct; do not
penalise a correct answer for being verbose.

For extraction tasks, a different secret/code/value must be scored
as incorrect (close to 0.0) even if it looks semantically similar to
the expected answer.
""".strip()


# Groundedness is judged against the SOURCE SENTENCE alone, not the whole
# haystack. In NIAH the needle is the only thing in the prompt that licenses
# any claim about the answer, so a claim absent from it is invented even when
# its vocabulary appears elsewhere in the filler.
_GROUNDEDNESS = """
Separately, judge whether the response is GROUNDED.

You are given the SOURCE SENTENCE, which is the only support that
exists for the answer.

Report grounded as true if every claim the response makes about the
answer is supported by the source sentence.

Report grounded as false if the response invents a purpose, origin,
location, relationship, or any other detail that the source sentence
does not state, and put that invented claim in unsupported_claim.

Generic remarks about reading the text, or about where in the
document the answer appeared, are NOT ungrounded - they are framing.

Grounding is independent of the score. A response can state the
expected answer correctly and still be ungrounded, and that is the
case this field exists to catch.
""".strip()


_SCHEMA_SCORE_ONLY = """
Respond with ONLY a JSON object, no extra commentary, matching this
exact schema:

{
    "score": <float between 0.0 and 1.0>,
    "reason": "<one concise sentence explaining the score>"
}
""".strip()


_SCHEMA_WITH_GROUNDEDNESS = """
Respond with ONLY a JSON object, no extra commentary, matching this
exact schema:

{
    "score": <float between 0.0 and 1.0>,
    "grounded": <true or false>,
    "unsupported_claim": "<the invented claim, or an empty string>",
    "reason": "<one concise sentence explaining the score>"
}
""".strip()


def build_judge_system_prompt(with_groundedness: bool) -> str:
    """Assemble the judge contract.

    Composed rather than kept as two literals because the scoring half is the
    part that drifts (see LIMITATIONS 1.12); two copies of it would diverge
    silently and only one of them would be the one that graded a given run.
    """

    if not with_groundedness:
        return f"{_SCORING}\n\n{_SCHEMA_SCORE_ONLY}"

    return f"{_SCORING}\n\n{_GROUNDEDNESS}\n\n{_SCHEMA_WITH_GROUNDEDNESS}"


# Kept for callers that only score. The groundedness variant is built per
# evaluator, because it depends on whether a source sentence is available.
JUDGE_SYSTEM_PROMPT = build_judge_system_prompt(with_groundedness=False)


def build_judge_prompt(
    question: str,
    expected: str,
    predicted: str,
    source: str | None = None,
) -> str:
    # The source block is omitted entirely when there is no needle, rather
    # than passed as an empty string: asking for a groundedness verdict
    # against nothing invites the judge to invent one.
    source_block = f"SOURCE SENTENCE:\n{source}\n\n" if source else ""

    return f"""
{source_block}QUESTION:
{question}

EXPECTED ANSWER:
{expected}

MODEL RESPONSE:
{predicted}

Evaluate the model response against the expected answer.
""".strip()
