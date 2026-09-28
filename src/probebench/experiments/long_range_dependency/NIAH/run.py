"""NIAH's three family-specific pieces. Everything else is in the pipeline.

Collapsed from 485 lines to this when D-021 extracted `experiments/pipeline.py`.
What remains is exactly what a second experiment would have to differ on: which
cases, which evaluators. The `FILLER_PATH` / `NEEDLES_PATH` module constants
went with the extraction - `NiahParams` had already become the source of truth
for both paths and nothing read them, so they were a second, stale copy of a
measured value.
"""

import logging
from pathlib import Path

from probebench.benchmarks.long_range_dependency.NIAH.benchmark import NiahBenchmark
from probebench.benchmarks.long_range_dependency.NIAH.settings import NiahParams
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
    # Validated here rather than in core/: the benchmark owns these knobs, so a
    # typo in one of them raises in the package that knows what they mean.
    params = NiahParams(**config.experiment_params)

    benchmark = NiahBenchmark(
        filler_path=params.filler_path,
        needles_path=params.needles_path,
        question=params.question,
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

    cases = benchmark.cases_as_generic()

    return CaseBundle(cases=cases, skipped=benchmark.skipped)


def _build_evaluators(config: RunConfig) -> list[Evaluator]:
    evaluators: list[Evaluator] = [
        LexicalEvaluator(),
        # Rules before models (invariant 9). Compliance is a syntactic property
        # of a string already in hand, so it is decided offline and for free -
        # and deliberately NOT gated behind --judge or --embedding, because a
        # metric that only exists when a judge was configured could not be
        # replayed over the archive.
        InstructionComplianceEvaluator(),
    ]

    # semantic_similarity was dropped from NIAH in D-019. J-022 showed it was
    # not a weak correctness signal but a near-perfect detector of response
    # FORM (min 0.9918 bare vs max 0.7977 prose, zero overlap over 424
    # records) - the same property InstructionComplianceEvaluator now decides
    # exactly, offline, with a recorded rule version. The class is retained for
    # future families whose expected answers are prose.

    if config.judge.enabled:
        judge_model = config.resolved_judge_model()

        # Self-judging is LIMITATIONS 1.2. J-006 showed it is not a mild bias:
        # qwen3:0.6b grading its own correct answers returned 0.0 with reasons
        # that named the expected string in the clause calling it missing.
        # Warn rather than refuse - a self-judged run is a legitimate thing to
        # ask for, it is just not a reportable one.
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


NIAH_PLUG = ExperimentPlug(
    build_cases=_build_cases,
    build_evaluators=_build_evaluators,
    # NIAH stopped scoring with embeddings in D-019, but the model is still
    # ensured present: the corpus-similarity analysis embeds needles and filler
    # windows offline, and a missing model should fail at startup rather than
    # halfway through an analysis.
    needs_embedding_model=True,
)


def run_niah(config: RunConfig) -> Path:
    return run_experiment(config, NIAH_PLUG)
