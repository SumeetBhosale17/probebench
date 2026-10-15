import re
from collections import Counter, defaultdict

import pytest

from probebench.benchmarks.long_context_understanding.negative_retrieval.benchmark import (
    NegativeRetrievalBenchmark,
)
from probebench.benchmarks.long_context_understanding.negative_retrieval.settings import (
    NegativeRetrievalParams,
)
from probebench.benchmarks.long_range_dependency.haystack import load_filler
from probebench.core.config import JudgeConfig, RunConfig
from probebench.evaluation.long_context_understanding.negative_retrieval.answerability import (
    AnswerabilityEvaluator,
)
from probebench.evaluation.long_range_dependency.NIAH.judge import OllamaJudge
from probebench.experiments.long_context_understanding.negative_retrieval.run import (
    _build_evaluators,
)
from probebench.tokenizers.tiktoken import TiktokenTokenizer


@pytest.fixture(scope="module")
def tokenizer() -> TiktokenTokenizer:
    return TiktokenTokenizer("cl100k_base")


def _benchmark(tokenizer: TiktokenTokenizer) -> NegativeRetrievalBenchmark:
    params = NegativeRetrievalParams()
    return NegativeRetrievalBenchmark(
        filler_path=params.filler_path,
        entity_path=params.entity_path,
        tokenizer=tokenizer,
        target_tokens=[4_000],
        depths=[0.25, 0.5],
        entity_counts=(4, 8),
        system_prompt=params.system_prompt,
        context_buffer_tokens=512,
        max_context_tokens=40_960,
        tokenizer_provider="tiktoken",
        tokenizer_name="cl100k_base",
    )


def test_cases_are_paired_balanced_and_uniquely_identified(tokenizer) -> None:
    cases = _benchmark(tokenizer).cases_as_generic()

    assert len(cases) == 16
    assert len({case.case_id for case in cases}) == len(cases)
    assert len({case.metadata["case_key"] for case in cases}) == len(cases)
    assert len({case.metadata["case_fingerprint"] for case in cases}) == len(cases)

    conditions = Counter(case.metadata["answerable"] for case in cases)
    assert conditions == {True: 8, False: 8}

    pairs = defaultdict(list)
    for case in cases:
        pairs[case.metadata["pair_id"]].append(case)

    assert len(pairs) == 8
    for pair in pairs.values():
        assert len(pair) == 2
        present, absent = sorted(pair, key=lambda case: not case.metadata["answerable"])
        assert present.metadata["answerable"] is True
        assert absent.metadata["answerable"] is False

        present_context = present.prompt.split("\n\nQuestion:", 1)[0]
        absent_context = absent.prompt.split("\n\nQuestion:", 1)[0]
        assert present_context == absent_context

        inventory = present.metadata["needle_inventory"]
        assert len(inventory) == present.metadata["fact_count"]
        assert present.metadata["query_entity_id"] in {block["block_id"] for block in inventory}
        assert absent.metadata["query_entity_id"] not in {block["block_id"] for block in inventory}
        assert absent.metadata["query_entity_name"].casefold() not in absent_context.casefold()


def test_cases_request_nonzero_bucketed_context(tokenizer) -> None:
    cases = _benchmark(tokenizer).cases_as_generic()

    for case in cases:
        context_tokens = case.metadata["context_tokens"]
        num_ctx = case.metadata["model_options"]["num_ctx"]
        assert case.metadata["target_tokens"] - case.metadata["fact_count"] <= context_tokens
        assert context_tokens <= case.metadata["target_tokens"]
        assert num_ctx >= context_tokens
        assert num_ctx % 512 == 0


def test_full_target_ladder_reaches_each_requested_context(tokenizer) -> None:
    benchmark = _benchmark(tokenizer)
    benchmark.target_tokens = [4_000, 8_000, 16_000, 32_000]
    cases = benchmark.cases_as_generic()

    assert len(cases) == 64
    for case in cases:
        target_tokens = case.metadata["target_tokens"]
        context_tokens = case.metadata["context_tokens"]
        fact_count = case.metadata["fact_count"]
        assert target_tokens - fact_count <= context_tokens <= target_tokens


def test_nonce_facts_have_uniform_token_cost_and_are_not_in_seed_filler(
    tokenizer,
) -> None:
    params = NegativeRetrievalParams()
    cases = _benchmark(tokenizer).cases_as_generic()
    facts = {
        block["block_id"]: block for case in cases for block in case.metadata["needle_inventory"]
    }
    values = {block["value"] for block in facts.values()}
    evidence_costs = {len(tokenizer.encode(block["text"])) for block in facts.values()}
    value_costs = {len(tokenizer.encode(value)) for value in values}
    value_shapes = {re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", value)) for value in values}
    filler = load_filler(params.filler_path).casefold()

    assert len(values) == 8
    assert len(evidence_costs) == 1
    assert len(value_costs) == 1
    assert value_shapes == {"AAA-9999"}
    assert all(value.casefold() not in filler for value in values)


def test_fact_count_above_inventory_is_rejected(tokenizer) -> None:
    params = NegativeRetrievalParams()
    benchmark = NegativeRetrievalBenchmark(
        filler_path=params.filler_path,
        entity_path=params.entity_path,
        tokenizer=tokenizer,
        target_tokens=[4_000],
        depths=[0.5],
        entity_counts=(16,),
        system_prompt=params.system_prompt,
        max_context_tokens=40_960,
    )

    with pytest.raises(ValueError, match="only 8 answerable facts"):
        benchmark.cases_as_generic()


def test_cases_include_strict_exact_output_contract(tokenizer) -> None:
    case = _benchmark(tokenizer).cases_as_generic()[0]
    prompt = case.prompt.lower()

    assert "exact value" in prompt
    assert "no markdown" in prompt
    assert "no explanation" in prompt
    assert "no_evidence_found" in prompt


def test_answerability_evaluator_distinguishes_retrieval_and_abstention(
    tokenizer,
) -> None:
    cases = _benchmark(tokenizer).cases_as_generic()
    evaluator = AnswerabilityEvaluator()

    present = next(case for case in cases if case.metadata["answerable"])
    absent = next(case for case in cases if not case.metadata["answerable"])

    assert evaluator.evaluate(present, present.expected).score == 1.0
    assert evaluator.evaluate(present, "A different value").score == 0.0
    assert evaluator.evaluate(absent, "NO_EVIDENCE_FOUND").score == 1.0
    assert evaluator.evaluate(absent, "I think the answer is BBD-1000").score == 0.0
    assert evaluator.evaluate(present, present.expected).metadata["rule_version"] == "1.0"


def test_llm_judge_is_additive_and_only_created_when_enabled() -> None:
    config = RunConfig(
        benchmark_family="long_context_understanding",
        experiment="negative_retrieval",
        generation_model="qwen3:0.6b",
        judge=JudgeConfig(enabled=False),
    )
    evaluators = _build_evaluators(config)
    assert [evaluator.name for evaluator in evaluators] == ["answerability_exact_match"]

    config.judge = JudgeConfig(enabled=True, model="qwen3:4b", num_ctx=4096)
    evaluators = _build_evaluators(config)
    assert [evaluator.name for evaluator in evaluators] == [
        "answerability_exact_match",
        "llm_judge",
    ]
    judge = evaluators[1]
    assert isinstance(judge, OllamaJudge)
    assert judge.model_name == "qwen3:4b"
    assert judge.num_ctx == 4096
    assert judge.check_groundedness is False
