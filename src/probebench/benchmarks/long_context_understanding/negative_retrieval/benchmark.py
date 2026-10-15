import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from probebench.benchmarks.long_context_understanding.negative_retrieval.settings import (
    BACKGROUND_DEPTHS,
    DEFAULT_ABSTAIN_TOKEN,
)
from probebench.benchmarks.long_range_dependency.haystack import (
    Block,
    EncodedFiller,
    build_haystack,
    load_filler,
)
from probebench.core.case import BenchmarkCase
from probebench.core.case_identity import fingerprint, format_depth, sha256_text
from probebench.core.tokenizer import Tokenizer


@dataclass(frozen=True)
class EntityRecord:
    id: str
    name: str
    value: str
    evidence: str
    answerable: bool

    @classmethod
    def from_record(cls, row: dict[str, object]) -> "EntityRecord":
        answerable = row["answerable"]
        if not isinstance(answerable, bool):
            raise ValueError("Entity field 'answerable' must be a boolean.")

        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            value=str(row["value"]),
            evidence=str(row.get("evidence", "")),
            answerable=answerable,
        )


class NegativeRetrievalBenchmark:
    benchmark_family = "long_context_understanding"
    experiment_name = "negative_retrieval"

    def __init__(
        self,
        filler_path: str,
        entity_path: str,
        tokenizer: Tokenizer,
        target_tokens: list[int],
        depths: list[float],
        entity_counts: tuple[int, ...],
        system_prompt: str,
        context_buffer_tokens: int = 512,
        max_context_tokens: int | None = None,
        num_ctx_granularity: int = 512,
        tokenizer_provider: str = "unknown",
        tokenizer_name: str = "unknown",
        answer_contract: str | None = None,
    ) -> None:
        self.filler_path = filler_path
        self.entity_path = entity_path
        self.tokenizer = tokenizer
        self.target_tokens = target_tokens
        self.depths = depths
        self.entity_counts = entity_counts
        self.system_prompt = system_prompt
        self.answer_contract = answer_contract or (
            "Return exactly one string and nothing else: the exact value from the "
            "supplied text if it is present; otherwise return exactly "
            "NO_EVIDENCE_FOUND. No markdown, no quotes, no punctuation, no extra "
            "words, and no explanation."
        )
        self.context_buffer_tokens = context_buffer_tokens
        self.max_context_tokens = max_context_tokens
        self.num_ctx_granularity = num_ctx_granularity
        self.tokenizer_provider = tokenizer_provider
        self.tokenizer_name = tokenizer_name
        self.skipped: list[dict[str, object]] = []

    def _load_entities(self) -> tuple[list[EntityRecord], list[EntityRecord], str]:
        path = Path(self.entity_path)

        if not path.exists():
            raise FileNotFoundError(f"Missing entity corpus: {path}")

        corpus_text = path.read_text(encoding="utf-8")
        entities = [
            EntityRecord.from_record(json.loads(line))
            for line in corpus_text.splitlines()
            if line.strip()
        ]

        if not entities:
            raise ValueError(f"Entity corpus is empty: {path}")

        ids = [entity.id for entity in entities]
        names = [entity.name.casefold() for entity in entities]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Entity IDs must be unique in {path}.")
        if len(set(names)) != len(names):
            raise ValueError(f"Entity names must be unique in {path}.")

        answerable = [entity for entity in entities if entity.answerable]
        absent_queries = [entity for entity in entities if not entity.answerable]

        for entity in answerable:
            if not entity.name or not entity.value or not entity.evidence:
                raise ValueError(
                    f"Answerable entity {entity.id!r} needs name, value, and evidence."
                )
            if entity.value == DEFAULT_ABSTAIN_TOKEN:
                raise ValueError(f"Answerable entity {entity.id!r} uses the abstention token.")

        for entity in absent_queries:
            if entity.evidence or entity.value != DEFAULT_ABSTAIN_TOKEN:
                raise ValueError(
                    f"Absent query {entity.id!r} must have empty evidence and the abstention token."
                )

        if not answerable or not absent_queries:
            raise ValueError("Entity corpus needs answerable facts and absent-query records.")
        if max(self.entity_counts, default=0) > len(answerable):
            raise ValueError(
                f"Largest fact_count is {max(self.entity_counts)}, but the corpus has only "
                f"{len(answerable)} answerable facts."
            )

        return answerable, absent_queries, sha256_text(corpus_text)

    def cases_as_generic(self) -> list[BenchmarkCase]:
        answerable, absent_queries, entity_corpus_sha256 = self._load_entities()
        filler = self._build_filler(
            load_filler(self.filler_path),
            answerable + absent_queries,
        )
        encoded_filler = EncodedFiller.encode(filler, self.tokenizer)
        self.skipped = []
        cases: list[BenchmarkCase] = []

        for target_index, target_tokens in enumerate(self.target_tokens):
            for depth_index, depth in enumerate(self.depths):
                for count_index, fact_count in enumerate(self.entity_counts):
                    background_depths = self._select_background_depths(fact_count - 1)

                    for absent_index, absent_query in enumerate(absent_queries):
                        target_index_in_corpus = (
                            target_index + depth_index + count_index + absent_index
                        ) % len(answerable)
                        target_entity = answerable[target_index_in_corpus]
                        facts = [
                            answerable[(target_index_in_corpus + offset) % len(answerable)]
                            for offset in range(fact_count)
                        ]

                        blocks = [
                            Block(
                                block_id=fact.id,
                                role="target" if index == 0 else "fact",
                                subject=fact.name,
                                value=fact.value,
                                text=fact.evidence,
                                requested_depth=(
                                    depth if index == 0 else background_depths[index - 1]
                                ),
                            )
                            for index, fact in enumerate(facts)
                        ]

                        haystack = build_haystack(
                            filler=encoded_filler,
                            blocks=blocks,
                            target_tokens=target_tokens,
                            tokenizer=self.tokenizer,
                            block_template="\n\n{text}\n\n",
                        )
                        context = haystack.text
                        actual_tokens = self.tokenizer.count(context)
                        num_ctx = self._calculate_num_ctx(actual_tokens)
                        pair_id = (
                            f"nretr/t{target_tokens}/d{format_depth(depth)}"
                            f"/k{fact_count}/target-{target_entity.id}"
                            f"/absent-{absent_query.id}"
                        )

                        if (
                            self.max_context_tokens is not None
                            and num_ctx > self.max_context_tokens
                        ):
                            for condition in ("present", "absent"):
                                self.skipped.append(
                                    {
                                        "target_tokens": target_tokens,
                                        "depth": depth,
                                        "fact_count": fact_count,
                                        "num_ctx": num_ctx,
                                        "condition": condition,
                                        "reason": "exceeds_context_limit",
                                    }
                                )
                            continue

                        inventory = [asdict(block) for block in haystack.blocks]
                        cases.extend(
                            self._paired_cases(
                                pair_id=pair_id,
                                context=context,
                                inventory=inventory,
                                target_entity=target_entity,
                                absent_query=absent_query,
                                target_tokens=target_tokens,
                                actual_tokens=actual_tokens,
                                num_ctx=num_ctx,
                                fact_count=fact_count,
                                depth=depth,
                                filler_sha256=encoded_filler.sha256,
                                entity_corpus_sha256=entity_corpus_sha256,
                            )
                        )

        return cases

    def _build_filler(
        self,
        seed: str,
        entities: list[EntityRecord],
    ) -> str:
        departments = (
            "accounts",
            "inventory",
            "dispatch",
            "facilities",
            "training",
            "quality",
        )
        assets = ("scanner", "badge", "relay", "cabinet", "meter", "terminal")
        statuses = ("verified", "pending", "archived", "reconciled")
        parts = [seed.rstrip()]
        next_record = 100_000
        estimated_tokens = self.tokenizer.count(parts[0])
        minimum_tokens = max(self.target_tokens, default=0) + self.context_buffer_tokens

        def record_text(record_id: int) -> str:
            department = departments[record_id % len(departments)]
            asset = assets[(record_id // len(departments)) % len(assets)]
            status = statuses[(record_id // (len(departments) * len(assets))) % len(statuses)]
            return (
                f"Record {record_id}: department {department}; asset {asset}; "
                f"status {status}; cycle {record_id}."
            )

        while estimated_tokens < minimum_tokens:
            records = [
                record_text(record_id) for record_id in range(next_record, next_record + 128)
            ]
            chunk = "\n".join(records)
            parts.append(chunk)
            estimated_tokens += len(self.tokenizer.encode("\n" + chunk))
            next_record += len(records)

        filler = "\n".join(parts)
        while self.tokenizer.count(filler) < minimum_tokens:
            filler += "\n" + "\n".join(
                record_text(record_id) for record_id in range(next_record, next_record + 128)
            )
            next_record += 128

        filler_folded = filler.casefold()
        for entity in entities:
            forbidden = entity.value if entity.answerable else entity.name
            if forbidden.casefold() in filler_folded:
                raise ValueError(
                    f"Generated filler contains benchmark entity text for {entity.id!r}."
                )

        return filler

    @staticmethod
    def _select_background_depths(count: int) -> list[float]:
        if count < 0 or count > len(BACKGROUND_DEPTHS):
            raise ValueError(
                f"Cannot place {count} background facts: only "
                f"{len(BACKGROUND_DEPTHS)} slots are defined."
            )
        if count == 0:
            return []

        slots = len(BACKGROUND_DEPTHS)
        return [
            BACKGROUND_DEPTHS[math.floor((index + 0.5) * slots / count)] for index in range(count)
        ]

    def _calculate_num_ctx(self, actual_tokens: int) -> int:
        requested = actual_tokens + self.context_buffer_tokens
        if self.num_ctx_granularity > 1:
            requested = math.ceil(requested / self.num_ctx_granularity) * self.num_ctx_granularity
        return requested

    def _paired_cases(
        self,
        *,
        pair_id: str,
        context: str,
        inventory: list[dict[str, object]],
        target_entity: EntityRecord,
        absent_query: EntityRecord,
        target_tokens: int,
        actual_tokens: int,
        num_ctx: int,
        fact_count: int,
        depth: float,
        filler_sha256: str,
        entity_corpus_sha256: str,
    ) -> list[BenchmarkCase]:
        shared = {
            "pair_id": pair_id,
            "context": context,
            "inventory": inventory,
            "target_tokens": target_tokens,
            "actual_tokens": actual_tokens,
            "num_ctx": num_ctx,
            "fact_count": fact_count,
            "depth": depth,
            "filler_sha256": filler_sha256,
            "entity_corpus_sha256": entity_corpus_sha256,
        }
        return [
            self._build_case(query=target_entity, answerable=True, **shared),
            self._build_case(query=absent_query, answerable=False, **shared),
        ]

    def _build_case(
        self,
        *,
        pair_id: str,
        context: str,
        inventory: list[dict[str, object]],
        query: EntityRecord,
        answerable: bool,
        target_tokens: int,
        actual_tokens: int,
        num_ctx: int,
        fact_count: int,
        depth: float,
        filler_sha256: str,
        entity_corpus_sha256: str,
    ) -> BenchmarkCase:
        question = f"What is the value of {query.name}?"
        prompt = (
            f"{context}\n\n"
            f"Question: {question}\n"
            f"Answer contract: {self.answer_contract}\n"
            "Final answer:"
        )
        expected = query.value if answerable else DEFAULT_ABSTAIN_TOKEN
        prompt_sha256 = sha256_text(prompt)
        condition = "present" if answerable else "absent"
        case_key = f"{pair_id}/{condition}/query-{query.id}"
        case_fingerprint = fingerprint(
            {
                "experiment": self.experiment_name,
                "prompt_sha256": prompt_sha256,
                "system_prompt": self.system_prompt,
                "expected": expected,
                "target_tokens": target_tokens,
                "depth": format_depth(depth),
                "fact_count": fact_count,
                "query_entity_id": query.id,
                "answerable": answerable,
                "tokenizer_provider": self.tokenizer_provider,
                "tokenizer_name": self.tokenizer_name,
                "filler_sha256": filler_sha256,
                "entity_corpus_sha256": entity_corpus_sha256,
            }
        )

        return BenchmarkCase(
            case_id=case_key,
            benchmark=self.benchmark_family,
            prompt=prompt,
            expected=expected,
            metadata={
                "experiment": self.experiment_name,
                "family": self.benchmark_family,
                "case_key": case_key,
                "case_fingerprint": case_fingerprint,
                "prompt_sha256": prompt_sha256,
                "system_prompt": self.system_prompt,
                "answerable": answerable,
                "question": question,
                "query_entity_id": query.id,
                "query_entity_name": query.name,
                "pair_id": pair_id,
                "fact_count": fact_count,
                "target_tokens": target_tokens,
                "context_tokens": actual_tokens,
                "depth": depth,
                "needle_inventory": inventory,
                "filler_sha256": filler_sha256,
                "entity_corpus_sha256": entity_corpus_sha256,
                "tokenizer_provider": self.tokenizer_provider,
                "tokenizer_name": self.tokenizer_name,
                "model_options": {"num_ctx": num_ctx},
            },
        )
