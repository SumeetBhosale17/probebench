from dataclasses import dataclass, field

@dataclass
class TokenizerConfig:
    """Tokenizer configuration use to contruct/measure a benchmark."""

    provider: str
    name: str

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

@dataclass
class RunConfig:
    """Complete configuration for a ProbeBench run."""

    benchmark_family: str
    experiment: str

    generation_model: str

    requested_context_window: int | None = None

    tokenizer: TokenizerConfig = field(
        default_factory=lambda: TokenizerConfig(
            provider="tiktoken",
            name="cl100k_base",
        )
    )

    embedding: EmbeddingConfig = field(
        default_factory=EmbeddingConfig
    )

    judge: JudgeConfig = field(
        default_factory=JudgeConfig
    )

    output_dir: str = "results"