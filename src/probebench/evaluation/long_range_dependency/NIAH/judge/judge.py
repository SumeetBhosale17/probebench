import json
from dataclasses import dataclass
from typing import Any

import ollama

from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import (
    EvaluationResult,
    Evaluator,
    validate_score,
)
from probebench.evaluation.long_range_dependency.NIAH.judge.prompt import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
)

@dataclass
class JudgeDecision:
    score: float
    reason: str

class OllamaJudge(Evaluator):
    """LLM-as-a-judge evaluator backed by Ollama."""

    name = "llm_judge"

    def __init__(
            self,
            model_name: str,
            host: str = "http://localhost:11434",
            timeout: float = 6000.0,
    ) -> None:
        self.model_name = model_name
        self.client = ollama.Client(
            host=host,
            timeout=timeout,
        )

    def evaluate(
            self,
            case: BenchmarkCase,
            predicted: str,
    ) -> EvaluationResult:

        question=case.metadata.get(
            "question",
            "Evaluate the response against the expected answer.", 
        )

        prompt = build_judge_prompt(
            question=question,
            expected=case.expected,
            predicted=predicted,
        )

        response = self.client.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": JUDGE_SYSTEM_PROMPT,  
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            format="json",
            options={
                "temperature": 0
            }
        )

        raw_content = response["message"]["content"]

        try:
            payload: dict[str, Any] = json.loads(
                raw_content
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM judge returned invalid JSON: "
                f"{raw_content}"
            ) from exc

        if "score" not in payload:
            raise ValueError(
                "LLM judge response does not contain 'score'."
            )

        score = float(payload["score"])

        reason = str(
            payload.get(
                "reason",
                "",
            )
        )

        return EvaluationResult(
            name=self.name,
            score=validate_score(score),
            metadata={
                "judge_model": self.model_name,
                "judge_reason": reason
            },
        )