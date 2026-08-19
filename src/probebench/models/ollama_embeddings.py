import ollama

from probebench.core.embedding import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Ollama."""

    def __init__(
        self,
        model_name: str,
        host: str = "http://localhost:11434",
    ) -> None:
        self.model_name = model_name
        self.client = ollama.Client(host=host)

    def embed(
        self,
        text: str,
    ) -> list[float]:

        response = self.client.embed(
            model=self.model_name,
            input=text,
        )

        embeddings = response["embeddings"]

        if not embeddings:
            raise RuntimeError("Ollama returned no embeddings.")

        return embeddings[0]
