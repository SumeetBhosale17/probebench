from collections.abc import Iterable
from uuid import uuid4

from probebench.core.case import BenchmarkCase
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.model import Model
from probebench.core.result import BenchmarkResult


class BenchmarkRunner:
    """Run benchmark cases against a model."""

    def __init__(
        self,
        model: Model,
        evaluators: Iterable[Evaluator],
        config: RunConfig,
    ) -> None:

        self.model = model
        self.evaluators = list(evaluators)
        self.config = config

        if self.config.run_id is None:
            self.config.run_id = uuid4().hex[:12]

    def run_case(
        self,
        case: BenchmarkCase,
    ) -> BenchmarkResult:

        system_prompt = case.metadata.get("system_prompt")

        model_options = case.metadata.get(
            "model_options",
            {},
        )

        response = self.model.generate(
            case.prompt,
            system_prompt=system_prompt,
            **model_options,
        )

        metrics: dict[str, float] = {}
        evaluation_metadata: dict[str, object] = {}

        for evaluator in self.evaluators:
            evaluation = evaluator.evaluate(
                case,
                response.text,
            )

            metrics[evaluation.name] = evaluation.score

            if evaluation.metadata:
                evaluation_metadata[evaluation.name] = evaluation.metadata

        case_metadata = dict(case.metadata)

        case_metadata.pop(
            "system_prompt",
            None,
        )

        case_metadata.pop(
            "model_options",
            None,
        )

        run_metadata = {
            "generation_model": (self.config.generation_model),
            "requested_context_window": (self.config.requested_context_window),
            "tokenizer": {
                "provider": (self.config.tokenizer.provider),
                "name": (self.config.tokenizer.name),
            },
            "embedding": {
                "enabled": (self.config.embedding.enabled),
                "provider": (self.config.embedding.provider),
                "model": (self.config.embedding.model),
            },
            "judge": {
                "enabled": (self.config.judge.enabled),
                "provider": (self.config.judge.provider),
                "model": (self.config.resolved_judge_model()),
            },
        }

        return BenchmarkResult(
            run_id=self.config.run_id or "",
            benchmark=case.benchmark,
            experiment=(self.config.experiment),
            case_id=case.case_id,
            model=(
                response.metadata.get(
                    "model",
                    self.config.generation_model,
                )
            ),
            expected=case.expected,
            predicted=response.text,
            latency_sec=response.latency_sec,
            metrics=metrics,
            evaluation_metadata=(evaluation_metadata),
            case_metadata=case_metadata,
            run_metadata=run_metadata,
        )
