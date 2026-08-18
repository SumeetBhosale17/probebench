from collections.abc import Iterable

from probebench.core.case import BenchmarkCase
from probebench.core.evaluator import Evaluator
from probebench.core.model import Model
from probebench.core.result import BenchmarkResult


class BenchmarkRunner:
    """Runs the benchmark cases against a model and evaluates responses."""

    def __init__(
        self,
        model: Model,
        evaluators: Iterable[Evaluator],
    ) -> None:
        self.model = model
        self.evaluators = list(evaluators)

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        """Run one case and return all evaluation results."""

        system_prompt = case.metadata.get("system_prompt")
        model_options = case.metadata.get("model_options", {})

        response = self.model.generate(
            case.prompt,
            system_prompt=system_prompt,
            **model_options,
        )

        metrics = {}

        for evaluators in self.evaluators:
            evaluation = evaluators.evaluate(
                case,
                response.text,
            )

            metrics[evaluation.name] = evaluation.score

        metadata = dict(case.metadata)

        # Don't duplicate fields that are already explicit result fields.
        metadata.pop("system_prompt", None)
        metadata.pop("model_options", None)

        return BenchmarkResult(
            benchmark=case.benchmark,
            case_id=case.case_id,
            model=response.metadata.get(
                "model",
                getattr(self.model, "model_name", "unknown"),
            ),
            expected=case.expected,
            predicted=response.text,
            latency_sec=response.latency_sec,
            metrics=metrics,
            metadata=metadata,
        )
