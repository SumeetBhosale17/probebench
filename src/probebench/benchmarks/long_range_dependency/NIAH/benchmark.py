import logging
import math

from probebench.benchmarks.long_range_dependency.NIAH.generator import (
    count_tokens,
    create_haystack,
    extract_expected_answer,
    load_filler,
    load_needles,
)
from probebench.benchmarks.long_range_dependency.NIAH.identity import (
    build_case_fingerprint,
    build_case_key,
)
from probebench.benchmarks.long_range_dependency.NIAH.schemas import (
    NiahCase,
)
from probebench.core.case import BenchmarkCase
from probebench.core.case_identity import sha256_text
from probebench.core.tokenizer import Tokenizer

logger = logging.getLogger(__name__)


class NiahBenchmark:
    """Generate Needle in a haystack cases."""

    benchmark_family = "long_range_dependency"
    experiment_name = "needle_in_a_haystack"

    question = "What is the important secret mentioned in the text?"
    system_prompt = (
        "You are a precise extraction engine. "
        "Answer ONLY with the secret code found in the text. "
        "Do not add any explanation."
    )

    def __init__(
        self,
        filler_path: str,
        needles_path: str,
        tokenizer: Tokenizer,
        target_tokens: list[int],
        depths: list[float],
        needles_per_configuration: int = 5,
        context_buffer_tokens: int = 512,
        max_context_tokens: int | None = None,
        num_ctx_granularity: int = 512,
        tokenizer_provider: str = "unknown",
        tokenizer_name: str = "unknown",
        question: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.filler_path = filler_path
        self.needles_path = needles_path

        # The class attributes remain the defaults, so an unconfigured run is
        # byte-identical to the pre-config behaviour. LIMITATIONS 1.9 measured
        # needle wording at 19 points of accuracy, which makes the question's
        # wording a measured variable rather than scaffolding.
        self.question = question or type(self).question
        self.system_prompt = system_prompt or type(self).system_prompt

        self.tokenizer = tokenizer

        # Passed in rather than read off the Tokenizer, which exposes only
        # encode/decode. They are fingerprint components: two models given
        # "the same" 4,000-token haystack built with different tokenizers did
        # NOT see the same input (LIMITATIONS 1.1), and the fingerprint has to
        # say so.
        self.tokenizer_provider = tokenizer_provider
        self.tokenizer_name = tokenizer_name

        self.target_tokens = target_tokens
        self.depths = depths

        self.needles_per_configuration = needles_per_configuration

        self.context_buffer_tokens = context_buffer_tokens
        self.max_context_tokens = max_context_tokens

        # Ollama keys a llama-server runner on num_ctx, so a one-token
        # difference between two cases would spawn a second runner and evict
        # the first. Rounding to a shared bucket keeps them on one.
        self.num_ctx_granularity = num_ctx_granularity

        self.skipped: list[dict] = []

        # Digests of the two data files, filled in by generate_cases().
        # filler_sha256 is a fingerprint component - it is what detects the
        # haystack corpus being swapped underneath a set of results.
        # needles_sha256 is provenance only: it detects a needle's text being
        # edited IN PLACE, which a per-needle digest cannot (D-015).
        self.filler_sha256: str | None = None
        self.needles_sha256: str | None = None

        # Constant until the template/guard arms land. Held as attributes so
        # identity is computed from one place rather than from literals
        # scattered through the case builder.
        self.needle_template = "marked"
        self.tail_guard_tokens = 0

    def generate_cases(self) -> list[NiahCase]:
        """Generate all NIAH benchmark cases."""

        filler = load_filler(self.filler_path)
        needles = load_needles(self.needles_path)

        self.filler_sha256 = sha256_text(filler)
        self.needles_sha256 = sha256_text("\n".join(needles))

        selected_needles = needles[: self.needles_per_configuration]

        cases: list[NiahCase] = []

        case_number = 1

        self.skipped = []

        for target_tokens in self.target_tokens:
            for depth in self.depths:
                for needle in selected_needles:
                    context = create_haystack(
                        filler=filler,
                        needle=needle,
                        target_tokens=target_tokens,
                        depth=depth,
                        tokenizer=self.tokenizer,
                    )
                    actual_tokens = count_tokens(context, tokenizer=self.tokenizer)
                    if self._exceeds_context_limit(actual_tokens):
                        logger.warning(
                            "Skipping case: target_tokens=%d depth=%.2f "
                            "actual_tokens=%d exceeds max_context_tokens=%s",
                            target_tokens,
                            depth,
                            actual_tokens,
                            self.max_context_tokens,
                        )

                        self.skipped.append(
                            {
                                "target_tokens": target_tokens,
                                "depth": depth,
                                "actual_tokens": actual_tokens,
                                "max_context_tokens": self.max_context_tokens,
                                "reason": "exceeds_context_limit",
                            }
                        )
                        continue

                    expected_answer = extract_expected_answer(needle)

                    num_ctx = self._calculate_num_ctx(actual_tokens)

                    case_id = self._build_case_id(
                        target_tokens=target_tokens,
                        depth=depth,
                        case_number=case_number,
                    )

                    cases.append(
                        NiahCase(
                            case_id=case_id,
                            context=context,
                            question=self.question,
                            expected_answer=expected_answer,
                            needle=needle,
                            target_tokens=target_tokens,
                            actual_tokens=actual_tokens,
                            depth=depth,
                            model_options={
                                "num_ctx": num_ctx,
                            },
                        )
                    )

                    case_number += 1

        return cases

    def cases_as_generic(self):
        """
        Convert benchmark-specific cases into generic ProbeBench cases.
        """

        return [self._to_generic_case(case) for case in self.generate_cases()]

    def _to_generic_case(
        self,
        case: NiahCase,
    ) -> BenchmarkCase:
        """Convert one NIAH case to a generic case."""

        prompt = f"{case.context}\n\nQuestion: {case.question}"

        prompt_sha256 = sha256_text(prompt)

        return BenchmarkCase(
            case_id=case.case_id,
            benchmark=self.benchmark_family,
            prompt=prompt,
            expected=case.expected_answer,
            metadata={
                "experiment": self.experiment_name,
                "needle": case.needle,
                "question": case.question,
                "target_tokens": case.target_tokens,
                "context_tokens": case.actual_tokens,
                "depth": case.depth,
                "case_key": build_case_key(
                    target_tokens=case.target_tokens,
                    depth=case.depth,
                    needle=case.needle,
                    needle_template=self.needle_template,
                    tail_guard_tokens=self.tail_guard_tokens,
                ),
                "case_fingerprint": build_case_fingerprint(
                    experiment=self.experiment_name,
                    prompt_sha256=prompt_sha256,
                    system_prompt=self.system_prompt,
                    expected=case.expected_answer,
                    needle=case.needle,
                    target_tokens=case.target_tokens,
                    depth=case.depth,
                    tokenizer_provider=self.tokenizer_provider,
                    tokenizer_name=self.tokenizer_name,
                    filler_sha256=self.filler_sha256 or "",
                    needle_template=self.needle_template,
                    tail_guard_tokens=self.tail_guard_tokens,
                ),
                # The prompt itself is never stored - a 128k-token haystack per
                # case would make the archive unusable - but the digest still
                # detects corpus drift (D-012).
                "prompt_sha256": prompt_sha256,
                "needle_template": self.needle_template,
                "tail_guard_tokens": self.tail_guard_tokens,
                "filler_sha256": self.filler_sha256,
                "needles_sha256": self.needles_sha256,
                "system_prompt": self.system_prompt,
                "model_options": case.model_options,
            },
        )

    def _exceeds_context_limit(
        self,
        actual_tokens: int,
    ) -> bool:
        """Return whether a generated case exceeds the limit."""

        if self.max_context_tokens is None:
            return False

        return actual_tokens > self.max_context_tokens

    def _calculate_num_ctx(
        self,
        actual_tokens: int,
    ) -> int:
        """Calculate the model context requested for this case.

        The context must accommodate the generated
        haystack plus a small buffer for the question
        and model-side prompt formatting.
        """

        requested_context = actual_tokens + self.context_buffer_tokens

        # Round up to a shared bucket so every case at a given target size
        # asks Ollama for the same num_ctx and reuses one loaded runner.
        if self.num_ctx_granularity > 1:
            buckets = math.ceil(requested_context / self.num_ctx_granularity)
            requested_context = buckets * self.num_ctx_granularity

        if self.max_context_tokens is None:
            return requested_context

        return min(
            requested_context,
            self.max_context_tokens,
        )

    @staticmethod
    def _build_case_id(
        target_tokens: int,
        depth: float,
        case_number: int,
    ) -> str:
        """Build a stable identifier for an NIAH case."""

        return f"niah_{target_tokens}_{depth:.2f}_{case_number:04d}"
