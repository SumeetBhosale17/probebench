import logging
from pathlib import Path

from probebench.benchmarks.long_context_understanding.negative_retrieval.benchmark import (
    NegativeRetrievalBenchmark,
)
from probebench.benchmarks.long_context_understanding.negative_retrieval.settings import (
    NegativeRetrievalParams,
)
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.tokenizer import Tokenizer
from probebench.evaluation.long_context_understanding.negative_retrieval.answerability import (
    AnswerabilityEvaluator,
)
from probebench.evaluation.long_range_dependency.NIAH.judge import OllamaJudge
from probebench.experiments.pipeline import CaseBundle, ExperimentPlug, run_experiment

logger = logging.getLogger(__name__)


def _build_cases(
    config: RunConfig,
    tokenizer: Tokenizer,
    max_context_tokens: int | None,
) -> CaseBundle:
    params = NegativeRetrievalParams(**config.experiment_params)

    benchmark = NegativeRetrievalBenchmark(
        filler_path=params.filler_path,
        entity_path=params.entity_path,
        tokenizer=tokenizer,
        target_tokens=list(config.sweep.target_tokens),
        depths=list(config.sweep.depths),
        entity_counts=params.entity_counts,
        system_prompt=params.system_prompt,
        context_buffer_tokens=config.sweep.context_buffer_tokens,
        max_context_tokens=max_context_tokens,
        tokenizer_provider=config.tokenizer.provider,
        tokenizer_name=config.tokenizer.name,
        answer_contract=params.answer_contract,
    )

    return CaseBundle(cases=benchmark.cases_as_generic(), skipped=benchmark.skipped)


def _build_evaluators(config: RunConfig) -> list[Evaluator]:
    evaluators: list[Evaluator] = [AnswerabilityEvaluator()]

    if not config.judge.enabled:
        return evaluators

    judge_model = config.resolved_judge_model()
    if judge_model == config.generation_model:
        logger.warning(
            "Judge model %s IS the generation model: this run is self-judged and "
            "its llm_judge column is not independently reportable (LIMITATIONS 1.2). "
            "Pass --judge-model to use an independent judge.",
            judge_model,
        )

    evaluators.append(
        OllamaJudge(
            model_name=judge_model,
            num_ctx=config.judge.num_ctx,
            max_predicted_chars=config.judge.max_predicted_chars,
            keep_alive=config.execution.keep_alive,
            max_retries=config.execution.max_retries,
            retry_backoff_sec=config.execution.retry_backoff_sec,
            check_groundedness=False,
        )
    )

    return evaluators


NEGATIVE_RETRIEVAL_PLUG = ExperimentPlug(
    build_cases=_build_cases,
    build_evaluators=_build_evaluators,
    needs_embedding_model=False,
)


def run_negative_retrieval(config: RunConfig) -> Path:
    return run_experiment(config, NEGATIVE_RETRIEVAL_PLUG)
