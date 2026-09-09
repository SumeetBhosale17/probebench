"""The multi-hop experiment's family-specific pieces (D-021 pipeline)."""

import logging
from pathlib import Path

from probebench.benchmarks.long_range_dependency.NIAH_multihop.benchmark import (
    NiahMultihopBenchmark,
)
from probebench.benchmarks.long_range_dependency.NIAH_multihop.settings import (
    NiahMultihopParams,
)
from probebench.core.config import RunConfig
from probebench.core.evaluator import Evaluator
from probebench.core.tokenizer import Tokenizer
from probebench.evaluation.long_range_dependency.NIAH.compliance import (
    InstructionComplianceEvaluator,
)
from probebench.evaluation.long_range_dependency.NIAH.judge import OllamaJudge
from probebench.evaluation.long_range_dependency.NIAH.lexical import LexicalEvaluator
from probebench.experiments.pipeline import CaseBundle, ExperimentPlug, run_experiment

logger = logging.getLogger(__name__)


def _build_cases(
    config: RunConfig,
    tokenizer: Tokenizer,
    max_context_tokens: int | None,
) -> CaseBundle:
    params = NiahMultihopParams(**config.experiment_params)

    benchmark = NiahMultihopBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        registry_sizes=params.registry_sizes,
        pointer_subject=params.pointer_subject,
        system_prompt=params.system_prompt,
        tokenizer=tokenizer,
        target_tokens=config.sweep.target_tokens,
        depths=config.sweep.depths,
        needles_per_configuration=config.sweep.needles_per_configuration,
        context_buffer_tokens=config.sweep.context_buffer_tokens,
        max_context_tokens=max_context_tokens,
        tokenizer_provider=config.tokenizer.provider,
        tokenizer_name=config.tokenizer.name,
    )

    return CaseBundle(cases=benchmark.cases_as_generic(), skipped=benchmark.skipped)


def _build_evaluators(config: RunConfig) -> list[Evaluator]:
    evaluators: list[Evaluator] = [
        # ⚠️ KNOWN-OPTIMISTIC, as in the distractor family: the repudiation
        # guard needs the word "secret" and this family never says it
        # (LIMITATIONS 1.18, J-029). Retrieval figures are upper bounds until
        # the guard is rebuilt from phrasings actually observed here.
        LexicalEvaluator(),
        InstructionComplianceEvaluator(),
    ]

    if config.judge.enabled:
        judge_model = config.resolved_judge_model()

        if judge_model == config.generation_model:
            logger.warning(
                "Judge model %s IS the generation model: this run is "
                "self-judged and its llm_judge column is not reportable "
                "(LIMITATIONS 1.2, JOURNAL J-006). Pass --judge-model to "
                "use an independent judge.",
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
            )
        )

    return evaluators


NIAH_MULTIHOP_PLUG = ExperimentPlug(
    build_cases=_build_cases,
    build_evaluators=_build_evaluators,
    needs_embedding_model=False,
)


def run_niah_multihop(config: RunConfig) -> Path:
    return run_experiment(config, NIAH_MULTIHOP_PLUG)
