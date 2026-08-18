from typing import Any

import ollama

from probebench.core.model import Model, ModelResponse


class OllamaModel(Model):
    """Ollama-backed Probebench Model."""

    def __init__(
        self,
        model_name: str,
        host: str = "http://localhost:11434",
        timeout: float = 6000.0,
    ) -> None:
        self.model_name = model_name

        self.client = ollama.Client(
            host=host,
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

        import time

        start = time.perf_counter()

        response = self.client.chat(
            model=self.model_name,
            messages=messages,
            options=options,
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

        response = self.client.embed(
            model=model,
            input=text,
        )

        embeddings = response["embeddings"]

        if not embeddings:
            raise RuntimeError(f"Ollama returned no embedding for model '{model}'.")

        return embeddings[0]
