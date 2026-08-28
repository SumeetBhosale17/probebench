from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenizerConfig:
    """Tokenizer configuration use to contruct/measure a benchmark."""

    provider: str = "tiktoken"
    name: str = "cl100k_base"


@dataclass
class EmbeddingConfig:
    """Embedding configuration used by semantic evaluation."""

    enabled: bool = True
    provider: str = "ollama"
    model: str = "nomic-embed-text"


@dataclass
class JudgeConfig:
    """LLM-as-a-judge configuration."""

    enabled: bool = True
    provider: str = "ollama"
    model: str | None = None

    num_ctx: int = 4096
    max_predicted_chars: int = 4000


@dataclass
class SweepConfig:
    """Which NIAH cases to generate"""

    target_tokens: list[int] = field(default_factory=lambda: [4_000, 8_000, 16_000, 32_000])
    depths: list[float] = field(default_factory=lambda: [0.0, 0.25, 0.5, 0.75, 1.0])
    needles_per_configuration: int = 1
    context_buffer_tokens: int = 512


@dataclass
class ExecutionConfig:
    """How the run behaves under failure and memory pressure."""

    # Robustness
    continue_on_error: bool = True
    max_retries: int = 3
    retry_backoff_sec: float = 2.0

    # Performance
    two_phase: bool = True
    sort_cases_by_num_ctx: bool = True
    keep_alive: str = "30m"

    # Memory preflight
    enforce_memory_preflight: bool = True
    memory_headroom_fraction: float = 0.85
    kv_cache_bytes_per_element: int = 2  # f16=2, q8_0=1, q4_0=0.5

    dry_run: bool = False


@dataclass
class RunConfig:
    """Complete configuration for a ProbeBench run."""

    benchmark_family: str
    experiment: str

    generation_model: str

    requested_context_window: int | None = None

    tokenizer: TokenizerConfig = field(default_factory=TokenizerConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    judge: JudgeConfig = field(default_factory=JudgeConfig)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    output_dir: str = "results"

    run_id: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_judge_model(self) -> str:
        """Return the configured judge model."""

        if self.judge.model:
            return self.judge.model

        return self.generation_model
