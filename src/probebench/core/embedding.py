from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Provider capable of generating embeddings."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed several texts at once.

        The default implementation just loops; providers that support a
        real batch endpoint should override it.
        """

        return [self.embed(text) for text in texts]
