"""Two-hop resolution: a pointer names a location, the registry holds the codes.

The model must find the pointer, read which location it names, then find THAT
location's code. Returning any code present is not enough, which is the point:
a single-hop reader has a k-in-1 chance of being right and a rule tier can tell
the two apart, because the inventory says which block held which value.

⚠️ Not comparable with NIAH or with NIAH_distractor. Different task, different
question, different system prompt, and - unlike either - a correct answer
requires composing two lookups.
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
from probebench.benchmarks.long_range_dependency.NIAH_distractor.benchmark import (
    select_background_depths,
)
from probebench.benchmarks.long_range_dependency.NIAH_distractor.needles import (
    KeyedNeedle,
    load_keyed_needles,
)
from probebench.benchmarks.long_range_dependency.NIAH_multihop.identity import (
    build_case_fingerprint,
    build_case_key,
)
from probebench.benchmarks.long_range_dependency.NIAH_multihop.settings import (
    POINTER_QUESTION,
    POINTER_TEMPLATE,
)
from probebench.core.case import BenchmarkCase
from probebench.core.case_identity import format_depth, sha256_text
from probebench.core.tokenizer import Tokenizer

logger = logging.getLogger(__name__)


def rotate(needles: list[KeyedNeedle], offset: int) -> list[KeyedNeedle]:
    """Cyclically shift a registry layout by `offset` slots.

    The set is preserved and only the order changes, which is what makes rank
    and subject identity orthogonal across a full sweep (D-024). Rotating the
    needle FILE instead would change the set too, replacing the confound rather
    than removing it.
    """

    if not needles:
        return []

    offset %= len(needles)

    return needles[offset:] + needles[:offset]


class NiahMultihopBenchmark:
    """Generate two-hop cases over (length x pointer depth x registry size x hop)."""

    benchmark_family = "long_range_dependency"
    experiment_name = "needle_in_a_haystack_multihop"

    def __init__(
        self,
        filler_path: str,
        needles_path: str,
        tokenizer: Tokenizer,
        target_tokens: list[int],
        depths: list[float],
        registry_sizes: tuple[int, ...],
        pointer_subject: str,
        system_prompt: str,
        max_registry_rotations: int = 1,
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
        self.registry_sizes = registry_sizes
        self.max_registry_rotations = max_registry_rotations

        self.pointer_subject = pointer_subject
        self.system_prompt = system_prompt

        self.needles_per_configuration = needles_per_configuration

        self.context_buffer_tokens = context_buffer_tokens
        self.max_context_tokens = max_context_tokens
        self.num_ctx_granularity = num_ctx_granularity

        self.skipped: list[dict] = []

        self.filler_sha256: str | None = None
        self.needles_sha256: str | None = None

        self.needle_template = "marked"
        self.tail_guard_tokens = 0

    def cases_as_generic(self) -> list[BenchmarkCase]:
        filler = load_filler(self.filler_path)
        needles = load_keyed_needles(self.needles_path)

        if any(n.subject == self.pointer_subject for n in needles):
            raise ValueError(
                f"Pointer subject {self.pointer_subject!r} also has a registry entry: "
                "the question would have two valid readings."
            )

        encoded_filler = EncodedFiller.encode(filler, self.tokenizer)

        self.filler_sha256 = encoded_filler.sha256
        self.needles_sha256 = sha256_text(
            "\n".join(f"{n.id}|{n.subject}|{n.value}" for n in needles)
        )

        cases: list[BenchmarkCase] = []
        self.skipped = []

        for target_tokens in self.target_tokens:
            for depth in self.depths:
                for k in self.registry_sizes:
                    subjects = needles[:k]

                    # Taken BEFORE rotation, and deliberately so (D-024). The
                    # old code sliced the rotated list, which would have changed
                    # which subjects are tested as hops at the same time as it
                    # changed their ranks - reintroducing the confound rotation
                    # exists to remove, in a form harder to notice.
                    targets = subjects[: self.needles_per_configuration]

                    for rotation in range(min(k, self.max_registry_rotations)):
                        registry = rotate(subjects, rotation)

                        for target in targets:
                            case = self._build_case(
                                encoded_filler=encoded_filler,
                                registry=registry,
                                target=target,
                                target_tokens=target_tokens,
                                depth=depth,
                                rotation=rotation,
                            )

                            if case is not None:
                                cases.append(case)

        return cases

    def _build_case(
        self,
        encoded_filler: EncodedFiller,
        registry: list[KeyedNeedle],
        target: KeyedNeedle,
        target_tokens: int,
        depth: float,
        rotation: int = 0,
    ) -> BenchmarkCase | None:
        k = len(registry)

        pointer_text = POINTER_TEMPLATE.format(
            pointer=self.pointer_subject,
            target=target.subject,
        )

        registry_depths = select_background_depths(k)

        blocks = [
            Block(
                block_id="pointer",
                role="pointer",
                subject=self.pointer_subject,
                # A pointer carries no code. Empty rather than the answer's
                # value: the whole task is that the answer is NOT in this block,
                # and putting it here would make a rule tier score a single-hop
                # read as a correct two-hop one.
                value="",
                text=pointer_text,
                requested_depth=depth,
            )
        ]

        blocks.extend(
            Block(
                block_id=entry.id,
                role="target" if entry.id == target.id else "distractor",
                subject=entry.subject,
                value=entry.value,
                text=entry.text,
                requested_depth=entry_depth,
            )
            for entry, entry_depth in zip(registry, registry_depths, strict=True)
        )

        haystack = build_haystack(
            filler=encoded_filler,
            blocks=blocks,
            target_tokens=target_tokens,
            tokenizer=self.tokenizer,
        )

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
                    "registry_size": k,
                    "target_id": target.id,
                    "actual_tokens": actual_tokens,
                    "max_context_tokens": self.max_context_tokens,
                    "reason": "exceeds_context_limit",
                }
            )

            return None

        question = POINTER_QUESTION.format(pointer=self.pointer_subject)

        prompt = f"{haystack.text}\n\nQuestion: {question}"
        prompt_sha256 = sha256_text(prompt)

        registry_components = [
            {"id": block.block_id, "value": block.value, "depth": format_depth(d)}
            for block, d in sorted(
                ((b, b.requested_depth) for b in haystack.blocks if b.role != "pointer"),
                key=lambda pair: pair[1],
            )
        ]

        pointer_block = next(b for b in haystack.blocks if b.role == "pointer")

        return BenchmarkCase(
            case_id=f"niahmh_{target_tokens}_{depth:.2f}_k{k}_r{rotation}_{target.id}",
            benchmark=self.benchmark_family,
            prompt=prompt,
            expected=target.value,
            metadata={
                "experiment": self.experiment_name,
                # The POINTER, not the block holding the answer. It is the block
                # whose position is being varied and the one that defines the
                # case; the answer's block is in the inventory.
                "needle": pointer_text,
                "question": question,
                "target_tokens": target_tokens,
                "context_tokens": actual_tokens,
                "depth": depth,
                "registry_size": k,
                "pointer_subject": self.pointer_subject,
                "target_id": target.id,
                "target_subject": target.subject,
                # The two axes D-024 exists to separate, recorded explicitly so
                # an analysis subtracts rather than re-derives them. `target_rank`
                # is the position of the answer's entry in the registry; under
                # rotation it moves while `target_id` is held fixed, which is the
                # whole design.
                "registry_rotation": rotation,
                "target_rank": registry.index(target),
                "case_key": build_case_key(
                    target_tokens=target_tokens,
                    depth=depth,
                    pointer_subject=self.pointer_subject,
                    target_id=target.id,
                    registry=[
                        {"id": item["id"], "depth": item["depth"]} for item in registry_components
                    ],
                    needle_template=self.needle_template,
                    tail_guard_tokens=self.tail_guard_tokens,
                ),
                "case_fingerprint": build_case_fingerprint(
                    experiment=self.experiment_name,
                    prompt_sha256=prompt_sha256,
                    system_prompt=self.system_prompt,
                    expected=target.value,
                    needle=pointer_text,
                    target_tokens=target_tokens,
                    depth=depth,
                    tokenizer_provider=self.tokenizer_provider,
                    tokenizer_name=self.tokenizer_name,
                    filler_sha256=self.filler_sha256 or "",
                    needle_template=self.needle_template,
                    tail_guard_tokens=self.tail_guard_tokens,
                    distractors=registry_components,
                ),
                "prompt_sha256": prompt_sha256,
                "needle_inventory": [asdict(block) for block in haystack.blocks],
                "realised_depth": pointer_block.realised_depth,
                "filler_tokens_used": haystack.filler_tokens_used,
                "needle_template": self.needle_template,
                "tail_guard_tokens": self.tail_guard_tokens,
                "filler_sha256": self.filler_sha256,
                "needles_sha256": self.needles_sha256,
                "system_prompt": self.system_prompt,
                "model_options": {"num_ctx": self._calculate_num_ctx(actual_tokens)},
            },
        )

    def _calculate_num_ctx(self, actual_tokens: int) -> int:
        requested_context = actual_tokens + self.context_buffer_tokens

        if self.num_ctx_granularity > 1:
            buckets = math.ceil(requested_context / self.num_ctx_granularity)
            requested_context = buckets * self.num_ctx_granularity

        if self.max_context_tokens is None:
            return requested_context

        return min(requested_context, self.max_context_tokens)
