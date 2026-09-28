"""The keyed distractor experiment's three family-specific pieces.

Everything else - the KV probe ordering, the memory preflight, the two-phase
split - is in `experiments/pipeline.py` (D-021). This file is what differs.
"""

import logging
from pathlib import Path

from probebench.benchmarks.long_range_dependency.NIAH_distractor.benchmark import (
    NiahDistractorBenchmark,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.settings import (
    NiahDistractorParams,
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
    params = NiahDistractorParams(**config.experiment_params)

    benchmark = NiahDistractorBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        system_prompt=params.system_prompt,
        distractor_counts=params.distractor_counts,
        tokenizer=tokenizer,
        target_tokens=config.sweep.target_tokens,
        depths=config.sweep.depths,
        needles_per_configuration=config.sweep.needles_per_configuration,
        context_buffer_tokens=config.sweep.context_buffer_tokens,
        max_context_tokens=max_context_tokens,
        tokenizer_provider=config.tokenizer.provider,
        tokenizer_name=config.tokenizer.name,
    )

    cases = benchmark.cases_as_generic()

    return CaseBundle(cases=cases, skipped=benchmark.skipped)


def _build_evaluators(config: RunConfig) -> list[Evaluator]:
    evaluators: list[Evaluator] = [
        # ⚠️ KNOWN-OPTIMISTIC HERE. LexicalEvaluator's repudiation guard needs
        # the literal word "secret" in two of its eight branches, because every
        # phrasing D-011 harvested came from NIAH's question. This family asks
        # "What is the access code for {subject}?", so its natural refusal -
        # "There is no access code for Brightwater in the text" - matches no
        # branch and scores 1.0 (J-029, LIMITATIONS 1.18). First-run retrieval
        # figures from this experiment are UPPER BOUNDS and must be reported as
        # such. The fix is to harvest real phrasings from this corpus and then
        # extend the guard - never to widen it speculatively, which is what
        # D-011 forbids.
        LexicalEvaluator(),
        # Rules before models (invariant 9). The answer space is a single token
        # here as in NIAH, so the rule applies unchanged.
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


NIAH_DISTRACTOR_PLUG = ExperimentPlug(
    build_cases=_build_cases,
    build_evaluators=_build_evaluators,
    # No embedding model is needed: D-019 dropped semantic scoring, and unlike
    # NIAH this family has no offline corpus-similarity analysis pending.
    needs_embedding_model=False,
)


def run_niah_distractor(config: RunConfig) -> Path:
    return run_experiment(config, NIAH_DISTRACTOR_PLUG)
