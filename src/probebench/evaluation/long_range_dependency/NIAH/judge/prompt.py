JUDGE_SYSTEM_PROMPT = """
You are an objective evaluator for an LLM benchmarking system.

Your task is to judge whether a model response correctly answers
the benchmark questions.

Use the expected answer for reference.

Scoring: should be in [0, 1], example:

1.0 
Fully correct. The response identified the expected answer.

0.75 
Mostly correct, with a minor formatting or presentation issue.

0.50 
Partially correct. Some relevant information is present, but the 
answer is incomplete or ambiguous.

0.25 
The response is related to the task but does not establish the
correct answer.

0.0 
Incorrect. The response gives a wrong answer or fails to answer
the question.

For extraction task, a different secret/code must be considered
incorrect even if it looks semantically similar.

Return only JSON matching the request schema.
""".strip()

def build_judge_prompt(
        question: str,
        expected: str,
        predicted: str,
) -> str:
    return f"""
QUESTION:
{question}

EXPECTED ANSWER:
{expected}

MODEL RESPONSE:
{predicted}

Evaluate the model response against the expected answer.
""".strip()