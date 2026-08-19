from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Provider capable of generating embeddings."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError
