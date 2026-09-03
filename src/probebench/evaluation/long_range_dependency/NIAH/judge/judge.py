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
    build_judge_prompt,
    build_judge_system_prompt,
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
        check_groundedness: bool = True,
    ) -> None:
        self.model_name = model_name
        self.num_ctx = num_ctx
        self.max_predicted_chars = max_predicted_chars
        self.keep_alive = keep_alive
        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec
        self.check_groundedness = check_groundedness

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

        # The needle is the only support in the prompt for any claim about the
        # answer, so it is what groundedness is judged against. A case without
        # one is scored but not grounded-checked, rather than checked against
        # nothing (D-010).
        source = case.metadata.get("needle") if self.check_groundedness else None

        prompt = build_judge_prompt(
            question=question,
            expected=case.expected,
            # A model that echoes its haystack would otherwise overflow the
            # pinned num_ctx below and silently truncate the grading rubric.
            predicted=self._truncate(predicted),
            source=source,
        )

        response = with_retries(
            lambda: self.client.chat(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": build_judge_system_prompt(with_groundedness=source is not None),
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

        # An out-of-range score is a judge failure, not a number to repair.
        # Rescaling 100.0 to 1.0 would be guessing at intent, and it would
        # hide the prompt regression that produced it (JOURNAL J-006). Raise
        # instead, and carry the payload in the message: the runner records
        # only the exception string, so anything not in here is lost, and the
        # rule tier cannot be replayed offline against evidence that no longer
        # exists.
        if not 0.0 <= score <= 1.0:
            raise JudgeError(
                f"judge returned a score outside [0.0, 1.0]: {score!r}; "
                f"reason={reason[:200]!r}; raw={raw_content[:300]!r}"
            )

        metadata: dict[str, Any] = {
            "judge_model": self.model_name,
            "judge_reason": reason,
        }

        if source is not None:
            metadata.update(self._grounding_metadata(payload))

        return EvaluationResult(
            name=self.name,
            score=validate_score(score),
            metadata=metadata,
        )

    @staticmethod
    def _grounding_metadata(payload: dict[str, Any]) -> dict[str, Any]:
        """Extract the groundedness label, or nothing at all.

        Invariant 8 applied to this field: a missing or non-boolean `grounded`
        leaves the key ABSENT, it does not default to True. Synthesising
        "grounded" for a case the judge never labelled would put a clean verdict
        on unlabelled data, which is the one thing the label cannot survive.

        A bad label invalidates only the label - the score has already been
        validated and still records (D-010).
        """

        grounded = payload.get("grounded")

        # Deliberately not truthiness: a string "false" or an int 0 means the
        # judge ignored the contract, and guessing which way it meant is how a
        # fabricated case becomes a clean one.
        if not isinstance(grounded, bool):
            return {}

        metadata: dict[str, Any] = {"grounded": grounded}

        claim = str(payload.get("unsupported_claim", "")).strip()

        # The claim is the evidence that makes the label auditable offline
        # without re-running the judge, so it is recorded whenever it exists.
        if claim:
            metadata["unsupported_claim"] = claim

        return metadata

    def _truncate(self, text: str) -> str:
        """Cap the graded response so it cannot overflow the pinned context."""

        if len(text) <= self.max_predicted_chars:
            return text

        dropped = len(text) - self.max_predicted_chars

        return text[: self.max_predicted_chars] + f"\n...[truncated {dropped} chars]"
