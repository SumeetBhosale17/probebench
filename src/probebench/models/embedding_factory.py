from probebench.core.config import EmbeddingConfig
from probebench.core.embedding import EmbeddingProvider
from probebench.models.ollama_embeddings import OllamaEmbeddingProvider


def create_embedding_provider(
        config: EmbeddingConfig,
) -> EmbeddingProvider | None:

    if not config.enabled:
        return None

    if config.provider == "ollama":
        return OllamaEmbeddingProvider(
            model_name=config.model
        )

    raise ValueError(
        f"Unsupported embedding provider: "
        f"{config.provider}"
    )