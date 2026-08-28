import logging
from collections.abc import Iterable
from uuid import uuid4

from probebench.core.case import BenchmarkCase
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.model import Model, ModelResponse
from probebench.core.result import BenchmarkResult

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Run benchmark cases against a model.

    Generation and evaluation are separable so a caller can run every
    generation first and only then run the evaluators. That keeps Ollama on
    one loaded runner per phase instead of swapping between the generation
    model and the judge model on every single case.
    """

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
        """Generate and evaluate one case in a single pass."""

        response, error = self.generate(case)

        return self.evaluate(case, response, error)

    def generate(
        self,
        case: BenchmarkCase,
    ) -> tuple[ModelResponse, str | None]:
        """Phase 1: call the model.

        Returns the response plus an error string. When continue_on_error is
        set, a failed generation yields an empty response and a message rather
        than propagating, so one bad case cannot abort the whole run.
        """

        system_prompt = case.metadata.get("system_prompt")

        model_options = case.metadata.get(
            "model_options",
            {},
        )

        try:
            response = self.model.generate(
                case.prompt,
                system_prompt=system_prompt,
                **model_options,
            )

        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            if not self.config.execution.continue_on_error:
                raise

            logger.exception(
                "Generation failed for case %s",
                case.case_id,
            )

            return (
                ModelResponse(
                    text="",
                    latency_sec=0.0,
                    metadata={},
                ),
                f"{type(exc).__name__}: {exc}",
            )

        return response, None

    def evaluate(
        self,
        case: BenchmarkCase,
        response: ModelResponse,
        error: str | None = None,
    ) -> BenchmarkResult:
        """Phase 2: run every evaluator over an already-generated response."""

        metrics: dict[str, float] = {}
        evaluation_details: dict[str, object] = {}

        status = "ok" if error is None else "generation_error"

        if error is None:
            for evaluator in self.evaluators:
                try:
                    evaluation = evaluator.evaluate(
                        case,
                        response.text,
                    )

                except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                    if not self.config.execution.continue_on_error:
                        raise

                    logger.exception(
                        "Evaluator %s failed for case %s",
                        evaluator.name,
                        case.case_id,
                    )

                    if status == "ok":
                        status = "evaluation_error"

                    # Deliberately leave metrics[name] ABSENT rather than
                    # writing 0.0. A judge that failed to answer is missing
                    # data; scoring it zero would silently bias the results.
                    evaluation_details[evaluator.name] = {
                        "error": f"{type(exc).__name__}: {exc}",
                    }

                    continue

                metrics[evaluation.name] = evaluation.score

                if evaluation.metadata:
                    evaluation_details[evaluation.name] = evaluation.metadata

        case_metadata = dict(case.metadata)

        case_metadata.pop(
            "system_prompt",
            None,
        )

        model_options = case_metadata.pop(
            "model_options",
            {},
        )

        run_id = self.config.run_id

        if run_id is None:
            raise RuntimeError(
                "RunConfig.run_id must be assigned before executing benchmark cases."
            )

        model_name = response.metadata.get(
            "model",
            self.config.generation_model,
        )

        return BenchmarkResult(
            run_id=run_id,
            benchmark=case.benchmark,
            experiment=(self.config.experiment),
            case_id=case.case_id,
            model_name=model_name,
            model_provider="ollama",
            expected=case.expected,
            predicted=response.text,
            latency_sec=response.latency_sec,
            metrics=metrics,
            evaluation_details=evaluation_details,
            case_metadata=case_metadata,
            model_metadata={
                "family": self.config.metadata.get("model_family"),
                "parameter_size": self.config.metadata.get("model_parameter_size"),
                "quantization": self.config.metadata.get("model_quantization"),
                "supported_context_window": self.config.metadata.get("supported_context_window"),
                "supported_context_source": self.config.metadata.get("supported_context_source"),
                "capabilities": self.config.metadata.get("model_capabilities"),
                "tokenizer_model": self.config.metadata.get("tokenizer_model"),
                "tokenizer_pre": self.config.metadata.get("tokenizer_pre"),
            },
            generation_metadata={
                "requested_context_window": self.config.requested_context_window,
                # The context actually asked of Ollama for this case, which is
                # what determines KV-cache cost and runner reuse.
                "num_ctx": model_options.get("num_ctx"),
                "kv_cache_bytes_per_element": (self.config.execution.kv_cache_bytes_per_element),
            },
            tokenization_metadata={
                "provider": self.config.tokenizer.provider,
                "name": self.config.tokenizer.name,
            },
            evaluation_metadata={
                "embedding": {
                    "enabled": self.config.embedding.enabled,
                    "provider": self.config.embedding.provider,
                    "model": self.config.embedding.model,
                },
                "judge": {
                    "enabled": self.config.judge.enabled,
                    "provider": self.config.judge.provider,
                    "model": self.config.resolved_judge_model(),
                    "num_ctx": self.config.judge.num_ctx,
                },
            },
            status=status,
            error=error,
        )
