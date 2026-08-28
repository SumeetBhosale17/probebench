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
from probebench.core.retry import with_retries
from probebench.evaluation.long_range_dependency.NIAH.judge.prompt import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
)
from probebench.models.host import default_ollama_host


class JudgeError(RuntimeError):
    """The judge model returned something unusable."""


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
        host: str | None = None,
        timeout: float = 6000.0,
        num_ctx: int = 4096,
        max_predicted_chars: int = 4000,
        keep_alive: str = "30m",
        max_retries: int = 3,
        retry_backoff_sec: float = 2.0,
    ) -> None:
        self.model_name = model_name
        self.num_ctx = num_ctx
        self.max_predicted_chars = max_predicted_chars
        self.keep_alive = keep_alive
        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec

        self.host = host or default_ollama_host()

        self.client = ollama.Client(
            host=self.host,
            timeout=timeout,
        )

    def evaluate(
        self,
        case: BenchmarkCase,
        predicted: str,
    ) -> EvaluationResult:

        question = case.metadata.get(
            "question",
            "Evaluate the response against the expected answer.",
        )

        prompt = build_judge_prompt(
            question=question,
            expected=case.expected,
            # A model that echoes its haystack would otherwise overflow the
            # pinned num_ctx below and silently truncate the grading rubric.
            predicted=self._truncate(predicted),
        )

        response = with_retries(
            lambda: self.client.chat(
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
                # Pinning num_ctx keeps the judge on ONE llama-server runner
                # for the whole run. Without it Ollama spawns a fresh runner
                # per distinct generation num_ctx and evicts the generation
                # model on every case.
                options={
                    "temperature": 0,
                    "num_ctx": self.num_ctx,
                },
                keep_alive=self.keep_alive,
                # Grading is a classification task; reasoning tokens on a
                # thinking model (qwen3) are pure latency here.
                think=False,
            ),
            attempts=self.max_retries,
            backoff_sec=self.retry_backoff_sec,
            description=f"judge chat({self.model_name})",
        )

        raw_content = response["message"]["content"]

        try:
            payload: dict[str, Any] = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"judge returned non-JSON: {raw_content[:300]!r}") from exc

        if "score" not in payload:
            raise JudgeError(f"judge response missing 'score': {raw_content[:300]!r}")

        try:
            score = float(payload["score"])
        except (TypeError, ValueError) as exc:
            raise JudgeError(f"judge returned a non-numeric score: {payload['score']!r}") from exc

        reason = str(
            payload.get(
                "reason",
                "",
            )
        )

        return EvaluationResult(
            name=self.name,
            score=validate_score(score),
            metadata={"judge_model": self.model_name, "judge_reason": reason},
        )

    def _truncate(self, text: str) -> str:
        """Cap the graded response so it cannot overflow the pinned context."""

        if len(text) <= self.max_predicted_chars:
            return text

        dropped = len(text) - self.max_predicted_chars

        return text[: self.max_predicted_chars] + f"\n...[truncated {dropped} chars]"
