"""Keyed-needle discrimination: k decoys plus one target, ask for one of them.

⚠️ THIS MEASURES A DIFFERENT TASK FROM NIAH. NIAH asks whether a model can find
the one code in a haystack; this asks whether it can find the RIGHT code among
k+1. Four independent things differ - needle wording (D-022), question, system
prompt, and retrieval versus discrimination - so distractor accuracy is not
comparable with NIAH accuracy on any axis. The k=0 cell exists to make the size
of that gap measurable rather than assumed (D-023).
"""

import logging
import math
from dataclasses import asdict

from probebench.benchmarks.long_range_dependency.haystack import (
    Block,
    EncodedFiller,
    build_haystack,
    load_filler,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.identity import (
    build_case_fingerprint,
    build_case_key,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.needles import (
    KeyedNeedle,
    load_keyed_needles,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.settings import (
    BACKGROUND_DEPTHS,
)
from probebench.core.case import BenchmarkCase
from probebench.core.case_identity import format_depth, sha256_text
from probebench.core.tokenizer import Tokenizer

logger = logging.getLogger(__name__)


def select_background_depths(k: int) -> list[float]:
    """Spread k decoys evenly over the eight background slots.

    Evenly rather than "the first k", which would put every k=1 decoy at 0.0625
    and confound the decoy COUNT with the decoy POSITION - at k=1 the single
    decoy would always be near the start, so a k-effect and a primacy effect
    would be indistinguishable.

    The slots are sixteenths and the target sweeps tenths, so a decoy can never
    take the target's index; `build_haystack` raises on a collision rather than
    repairing one, and this is what keeps that unreachable.
    """

    if k <= 0:
        return []

    if k > len(BACKGROUND_DEPTHS):
        raise ValueError(
            f"Cannot place {k} decoys: only {len(BACKGROUND_DEPTHS)} background "
            "slots are defined, and adding slots changes what every existing "
            "case measures."
        )

    slots = len(BACKGROUND_DEPTHS)

    return [BACKGROUND_DEPTHS[math.floor((i + 0.5) * slots / k)] for i in range(k)]


class NiahDistractorBenchmark:
    """Generate keyed discrimination cases over (length x depth x k x target)."""

    benchmark_family = "long_range_dependency"
    experiment_name = "needle_in_a_haystack_distractor"

    def __init__(
        self,
        filler_path: str,
        needles_path: str,
        tokenizer: Tokenizer,
        target_tokens: list[int],
        depths: list[float],
        distractor_counts: tuple[int, ...],
        system_prompt: str,
        needles_per_configuration: int = 5,
        context_buffer_tokens: int = 512,
        max_context_tokens: int | None = None,
        num_ctx_granularity: int = 512,
        tokenizer_provider: str = "unknown",
        tokenizer_name: str = "unknown",
    ) -> None:
        self.filler_path = filler_path
        self.needles_path = needles_path

        self.tokenizer = tokenizer
        self.tokenizer_provider = tokenizer_provider
        self.tokenizer_name = tokenizer_name

        self.target_tokens = target_tokens
        self.depths = depths
        self.distractor_counts = distractor_counts

        self.system_prompt = system_prompt

        self.needles_per_configuration = needles_per_configuration

        self.context_buffer_tokens = context_buffer_tokens
        self.max_context_tokens = max_context_tokens

        # Ollama keys a runner on num_ctx (R-002, invariant 3).
        self.num_ctx_granularity = num_ctx_granularity

        self.skipped: list[dict] = []

        self.filler_sha256: str | None = None
        self.needles_sha256: str | None = None

        # Same arm defaults as NIAH, so the k=0 cell differs from a NIAH case in
        # exactly the ways D-022 names and in no others.
        self.needle_template = "marked"
        self.tail_guard_tokens = 0

    def cases_as_generic(self) -> list[BenchmarkCase]:
        filler = load_filler(self.filler_path)
        needles = load_keyed_needles(self.needles_path)

        encoded_filler = EncodedFiller.encode(filler, self.tokenizer)

        self.filler_sha256 = encoded_filler.sha256
        self.needles_sha256 = sha256_text(
            "\n".join(f"{n.id}|{n.subject}|{n.value}" for n in needles)
        )

        targets = needles[: self.needles_per_configuration]

        cases: list[BenchmarkCase] = []
        self.skipped = []

        for target_tokens in self.target_tokens:
            for depth in self.depths:
                for k in self.distractor_counts:
                    for target in targets:
                        case = self._build_case(
                            encoded_filler=encoded_filler,
                            needles=needles,
                            target=target,
                            target_tokens=target_tokens,
                            depth=depth,
                            k=k,
                        )

                        if case is not None:
                            cases.append(case)

        return cases

    def _build_case(
        self,
        encoded_filler: EncodedFiller,
        needles: list[KeyedNeedle],
        target: KeyedNeedle,
        target_tokens: int,
        depth: float,
        k: int,
    ) -> BenchmarkCase | None:
        decoys = self._select_decoys(needles, target, k)
        background_depths = select_background_depths(k)

        blocks = [
            Block(
                block_id=target.id,
                role="target",
                subject=target.subject,
                value=target.value,
                text=target.text,
                requested_depth=depth,
            )
        ]

        blocks.extend(
            Block(
                block_id=decoy.id,
                role="distractor",
                subject=decoy.subject,
                value=decoy.value,
                text=decoy.text,
                requested_depth=decoy_depth,
            )
            for decoy, decoy_depth in zip(decoys, background_depths, strict=True)
        )

        haystack = build_haystack(
            filler=encoded_filler,
            blocks=blocks,
            target_tokens=target_tokens,
            tokenizer=self.tokenizer,
        )

        # Counted from the TEXT, never from haystack.total_tokens: splicing
        # yields a non-canonical token sequence and the served text re-encodes
        # shorter in 27% of cases (J-030, LIMITATIONS 1.19).
        actual_tokens = self.tokenizer.count(haystack.text)

        if self.max_context_tokens is not None and actual_tokens > self.max_context_tokens:
            logger.warning(
                "Skipping case: target_tokens=%d depth=%.2f k=%d actual_tokens=%d "
                "exceeds max_context_tokens=%s",
                target_tokens,
                depth,
                k,
                actual_tokens,
                self.max_context_tokens,
            )

            self.skipped.append(
                {
                    "target_tokens": target_tokens,
                    "depth": depth,
                    "distractor_count": k,
                    "target_id": target.id,
                    "actual_tokens": actual_tokens,
                    "max_context_tokens": self.max_context_tokens,
                    "reason": "exceeds_context_limit",
                }
            )

            return None

        prompt = f"{haystack.text}\n\nQuestion: {target.question}"
        prompt_sha256 = sha256_text(prompt)

        inventory = [asdict(block) for block in haystack.blocks]

        # Formatted depths, and only the fields that determine the INPUT. The
        # realised depth is an output of placement, so including it would make
        # the fingerprint depend on its own construction.
        distractor_components = [
            {"id": block.block_id, "value": block.value, "depth": format_depth(d)}
            for block, d in sorted(
                ((b, b.requested_depth) for b in haystack.blocks if b.role == "distractor"),
                key=lambda pair: pair[1],
            )
        ]

        background = [{"id": item["id"], "depth": item["depth"]} for item in distractor_components]

        target_block = next(b for b in haystack.blocks if b.role == "target")

        return BenchmarkCase(
            case_id=f"niahd_{target_tokens}_{depth:.2f}_k{k}_{target.id}",
            benchmark=self.benchmark_family,
            prompt=prompt,
            expected=target.value,
            metadata={
                "experiment": self.experiment_name,
                "needle": target.text,
                "question": target.question,
                "target_tokens": target_tokens,
                "context_tokens": actual_tokens,
                "depth": depth,
                "distractor_count": k,
                "target_id": target.id,
                "target_subject": target.subject,
                "case_key": build_case_key(
                    target_tokens=target_tokens,
                    depth=depth,
                    target_id=target.id,
                    background=background,
                    needle_template=self.needle_template,
                    tail_guard_tokens=self.tail_guard_tokens,
                ),
                "case_fingerprint": build_case_fingerprint(
                    experiment=self.experiment_name,
                    prompt_sha256=prompt_sha256,
                    system_prompt=self.system_prompt,
                    expected=target.value,
                    needle=target.text,
                    target_tokens=target_tokens,
                    depth=depth,
                    tokenizer_provider=self.tokenizer_provider,
                    tokenizer_name=self.tokenizer_name,
                    filler_sha256=self.filler_sha256 or "",
                    needle_template=self.needle_template,
                    tail_guard_tokens=self.tail_guard_tokens,
                    distractors=distractor_components,
                ),
                "prompt_sha256": prompt_sha256,
                # The whole point of the family. Every planted value with its
                # role and where it landed, so "returned a decoy" separates from
                # "fabricated a value" by a substring search over a known
                # inventory - offline, with no second model call.
                "needle_inventory": inventory,
                "realised_depth": target_block.realised_depth,
                "filler_tokens_used": haystack.filler_tokens_used,
                "needle_template": self.needle_template,
                "tail_guard_tokens": self.tail_guard_tokens,
                "filler_sha256": self.filler_sha256,
                "needles_sha256": self.needles_sha256,
                "system_prompt": self.system_prompt,
                "model_options": {"num_ctx": self._calculate_num_ctx(actual_tokens)},
            },
        )

    @staticmethod
    def _select_decoys(
        needles: list[KeyedNeedle],
        target: KeyedNeedle,
        k: int,
    ) -> list[KeyedNeedle]:
        """The k needles following the target in file order, wrapping around.

        Deterministic, so a cell rebuilds identically; and target-relative, so
        every target gets a different decoy set rather than all of them
        competing against the same first k. Which decoys were used is recorded
        per case regardless - the file is not trusted to stay put.
        """

        if k <= 0:
            return []

        others = [n for n in needles if n.id != target.id]

        if k > len(others):
            raise ValueError(f"Need {k} decoys but only {len(others)} other needles exist.")

        start = needles.index(target)

        return [others[(start + i) % len(others)] for i in range(k)]

    def _calculate_num_ctx(self, actual_tokens: int) -> int:
        requested_context = actual_tokens + self.context_buffer_tokens

        if self.num_ctx_granularity > 1:
            buckets = math.ceil(requested_context / self.num_ctx_granularity)
            requested_context = buckets * self.num_ctx_granularity

        if self.max_context_tokens is None:
            return requested_context

        return min(requested_context, self.max_context_tokens)
