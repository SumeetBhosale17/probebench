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
        think: bool | None = None,
    ) -> None:
        self.model_name = model_name

        # None means "do not pass `think` at all", which leaves the model at
        # its own default. That is what every archived run did, so None keeps
        # new runs comparable with them (J-017).
        #
        # Do NOT set this to False as a cost lever on qwen3:4b: the flag does
        # not disable reasoning there, it moves the chain of thought into
        # message.content, where the evaluators would score it.
        self.think = think

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

        # Only forwarded when set, so the default path is byte-identical to
        # what the archive was produced with.
        think_kwargs: dict[str, Any] = {} if self.think is None else {"think": self.think}

        response = with_retries(
            lambda: self.client.chat(
                model=self.model_name,
                messages=messages,
                options=options,
                keep_alive=self.keep_alive,
                **think_kwargs,
            ),
            attempts=self.max_retries,
            backoff_sec=self.retry_backoff_sec,
            description=(f"chat({self.model_name}, num_ctx={options.get('num_ctx')})"),
        )

        elapsed = time.perf_counter() - start

        message = response["message"]

        answer = message["content"].strip()

        # qwen3 reasons by default and the reasoning was being discarded
        # entirely - 175-241 decode tokens per case that no record mentioned,
        # and most of the generation cost at long context (J-017). The text
        # itself is not stored (it is large and not the object of study); its
        # length is the evidence that it happened.
        thinking = message.get("thinking") or ""

        return ModelResponse(
            text=answer,
            latency_sec=elapsed,
            metadata={
                "model": self.model_name,
                "think": self.think,
                "thinking_chars": len(thinking),
                # done_reason distinguishes a model that finished from one the
                # token budget cut off. Without it a truncated answer is
                # indistinguishable from a model that gave up, which is exactly
                # the ambiguity in J-011's five "dangling output" cases.
                "done_reason": response.get("done_reason"),
                # prompt_eval_count is the model's OWN token count for the
                # prompt. Haystacks are sized with cl100k and served to other
                # tokenizers (LIMITATIONS 1.1), so this is the only measured
                # x-axis we have - and the only way to see llama.cpp dropping
                # tokens from the front when a prompt exceeds num_ctx.
                "prompt_eval_count": response.get("prompt_eval_count"),
                "eval_count": response.get("eval_count"),
                # Server-side nanosecond timings. latency_sec above is client
                # wall-clock and includes retries and queueing behind the
                # judge; these separate prefill from decode.
                "prompt_eval_duration_ns": response.get("prompt_eval_duration"),
                "eval_duration_ns": response.get("eval_duration"),
                "load_duration_ns": response.get("load_duration"),
                "total_duration_ns": response.get("total_duration"),
            },
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
