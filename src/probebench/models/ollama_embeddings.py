import ollama

from probebench.core.embedding import EmbeddingProvider
from probebench.core.retry import with_retries
from probebench.models.host import default_ollama_host


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Ollama."""

    def __init__(
        self,
        model_name: str,
        host: str | None = None,
        max_retries: int = 3,
        retry_backoff_sec: float = 2.0,
    ) -> None:
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec

        self.host = host or default_ollama_host()
        self.client = ollama.Client(host=self.host)

    def embed(
        self,
        text: str,
    ) -> list[float]:

        return self.embed_batch([text])[0]

    def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed several texts in one request.

        The semantic evaluator needs the expected and predicted answers
        together, so batching halves the embedding round-trips per case.
        """

        response = with_retries(
            lambda: self.client.embed(
                model=self.model_name,
                input=texts,
            ),
            attempts=self.max_retries,
            backoff_sec=self.retry_backoff_sec,
            description=f"embed({self.model_name}, n={len(texts)})",
        )

        embeddings = response["embeddings"]

        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Ollama returned {len(embeddings)} embeddings for {len(texts)} inputs."
            )

        return embeddings
