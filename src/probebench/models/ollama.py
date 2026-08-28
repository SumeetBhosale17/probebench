import time
from typing import Any

import ollama

from probebench.core.model import Model, ModelResponse
from probebench.core.retry import with_retries
from probebench.models.host import default_ollama_host


class OllamaModel(Model):
    """Ollama-backed Probebench Model."""

    def __init__(
        self,
        model_name: str,
        host: str | None = None,
        timeout: float = 6000.0,
        keep_alive: str = "30m",
        max_retries: int = 3,
        retry_backoff_sec: float = 2.0,
    ) -> None:
        self.model_name = model_name

        # Holding the runner resident between cases avoids reloading several
        # GB of weights each time. It only helps when every call shares the
        # same num_ctx, which is why cases are sorted by num_ctx upstream.
        self.keep_alive = keep_alive

        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec

        self.host = host or default_ollama_host()

        self.client = ollama.Client(
            host=self.host,
            timeout=timeout,
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **options: Any,
    ) -> ModelResponse:

        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        start = time.perf_counter()

        response = with_retries(
            lambda: self.client.chat(
                model=self.model_name,
                messages=messages,
                options=options,
                keep_alive=self.keep_alive,
            ),
            attempts=self.max_retries,
            backoff_sec=self.retry_backoff_sec,
            description=(f"chat({self.model_name}, num_ctx={options.get('num_ctx')})"),
        )

        elapsed = time.perf_counter() - start

        answer = response["message"]["content"].strip()

        return ModelResponse(
            text=answer,
            latency_sec=elapsed,
            metadata={"model": self.model_name},
        )

    def embed(self, model: str, text: str) -> list[float]:
        """Generate an embedding using Ollama."""

        return self.embed_batch(model, [text])[0]

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        """Embed several texts in a single request."""

        response = with_retries(
            lambda: self.client.embed(
                model=model,
                input=texts,
            ),
            attempts=self.max_retries,
            backoff_sec=self.retry_backoff_sec,
            description=f"embed({model}, n={len(texts)})",
        )

        embeddings = response["embeddings"]

        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Ollama returned {len(embeddings)} embeddings "
                f"for {len(texts)} inputs using model '{model}'."
            )

        return embeddings
