from dataclasses import dataclass
from typing import Any

import ollama

from probebench.models.host import default_ollama_host


class MissingModelsError(RuntimeError):
    """One or more required models are not installed on the Ollama host.

    Carries the model names so callers can offer to pull them instead of
    only printing a message.
    """

    def __init__(
        self,
        missing: list[str],
        installed: list[str] | None = None,
    ) -> None:
        self.missing = missing
        self.installed = installed or []

        super().__init__(
            "Models not available on this Ollama host: "
            + ", ".join(missing)
            + "\nInstalled: "
            + (", ".join(self.installed) or "<none>")
            + "\n\nIf a model you expect is missing, check that you are talking to "
            "the Ollama server you think you are. A systemd `ollama` service and a "
            "user-launched `ollama serve` use different model stores "
            "(/usr/share/ollama/.ollama/models vs ~/.ollama/models) and both bind "
            ":11434. Check `ss -ltnp | grep 11434` and $OLLAMA_MODELS."
        )


@dataclass
class ModelInfo:
    """Normalized information about an Ollama model."""

    name: str

    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None

    context_length: int | None = None
    context_length_source: str | None = None

    capabilities: list[str] | None = None

    tokenizer_model: str | None = None
    tokenizer_pre: str | None = None

    raw: dict[str, Any] | None = None

    block_count: int | None = None  # n_layers
    kv_head_count: int | None = None  # n_kv_heads (GQA)
    head_count: int | None = None  # n_heads (attention); head_count/kv_head_count is the GQA ratio
    head_dim: int | None = None
    embedding_length: int | None = None
    size_bytes: int | None = None  # on-disk weight size

    def kv_bytes_per_token(self, bytes_per_element: int = 2) -> int | None:
        """Bytes of KV cache consumed per token of context.
        K and V, for every layer:
            2 * n_layers * n_kv_heads * head_dim * bytes_per_element
        """

        if not (self.block_count and self.kv_head_count and self.head_dim):
            return None

        return 2 * self.block_count * self.kv_head_count * self.head_dim * bytes_per_element

    def kv_cache_bytes(self, num_ctx: int, bytes_per_element: int = 2) -> int | None:

        per_token = self.kv_bytes_per_token(bytes_per_element)
        if per_token is None:
            return None
        return per_token * num_ctx


class OllamaModelRegistry:
    """Discover and inspect models available to Ollama."""

    def __init__(
        self,
        host: str | None = None,
    ) -> None:
        self.host = host or default_ollama_host()
        self.client = ollama.Client(host=self.host)

    def list_models(self) -> list[ModelInfo]:
        """Return locally installed Ollama models."""

        response = self.client.list()

        models: list[ModelInfo] = []

        for model in response.models:
            details = getattr(model, "details", None)

            models.append(
                ModelInfo(
                    name=model.model or "unknown",
                    family=getattr(
                        details,
                        "family",
                        None,
                    ),
                    parameter_size=getattr(
                        details,
                        "parameter_size",
                        None,
                    ),
                    quantization=getattr(
                        details,
                        "quantization_level",
                        None,
                    ),
                    size_bytes=getattr(
                        model,
                        "size",
                        None,
                    ),
                )
            )

        return models

    def inspect(
        self,
        model_name: str,
    ) -> ModelInfo:
        """Inspect detailed metadata for one Ollama model."""

        response = self.client.show(
            model=model_name,
            # verbose=True,
        )

        details = response.details

        model_info = dict(response.modelinfo or {})

        capabilities = [str(capability) for capability in (response.capabilities or [])]

        context_length, context_length_source = self._find_context_length(model_info)
        block_count = self._find_int(model_info, ".block_count")
        kv_head_count = self._find_int(model_info, ".attention.head_count_kv")
        head_dim = self._find_int(model_info, ".attention.key_length")
        embedding_length = self._find_int(model_info, ".embedding_length")
        head_count = self._find_int(model_info, ".attention.head_count")

        # some GGFUs omit key_length. Derive it: head_dim = d_model / n_heads.
        if head_dim is None and embedding_length and head_count:
            head_dim = embedding_length // head_count

        # `show` does not report on-disk size, so cross-reference `list`.
        size_bytes = None

        for installed in self.list_models():
            if installed.name == model_name or installed.name == f"{model_name}:latest":
                size_bytes = installed.size_bytes
                break

        tokenizer_model = self._find_string(
            model_info,
            "tokenizer.ggml.model",
        )

        tokenizer_pre = self._find_string(
            model_info,
            "tokenizer.ggml.pre",
        )

        raw = {
            "details": (details.model_dump() if details is not None else {}),
            "model_info": model_info,
            "capabilities": capabilities,
            "parameters": response.parameters,
            "template": response.template,
            "license": response.license,
        }

        return ModelInfo(
            name=model_name,
            family=getattr(
                details,
                "family",
                None,
            ),
            parameter_size=getattr(
                details,
                "parameter_size",
                None,
            ),
            quantization=getattr(
                details,
                "quantization_level",
                None,
            ),
            context_length=context_length,
            context_length_source=context_length_source,
            capabilities=capabilities,
            tokenizer_model=tokenizer_model,
            tokenizer_pre=tokenizer_pre,
            block_count=block_count,
            kv_head_count=kv_head_count,
            head_count=head_count,
            head_dim=head_dim,
            embedding_length=embedding_length,
            size_bytes=size_bytes,
            raw=raw,
        )

    def available_names(self) -> set[str]:
        """Every locally installed model name, including ':latest' aliases."""

        names: set[str] = set()
        for model in self.list_models():
            names.add(model.name)

            if model.name.endswith(":latest"):
                names.add(model.name.rsplit(":", 1)[0])
        return names

    def missing_models(self, *model_names: str) -> list[str]:
        """Return the requested models that are not installed on this host.

        Empty strings are ignored so callers can pass optional models
        (judge, embedding) without branching at the call site.
        """

        installed = self.available_names()

        return [
            name
            for name in dict.fromkeys(model_names)
            if name and name not in installed and f"{name}:latest" not in installed
        ]

    def ensure_availability(self, *model_names: str) -> None:
        """Fail fast if any required model is missing from this Ollama host."""

        missing = self.missing_models(*model_names)

        if not missing:
            return

        raise MissingModelsError(
            missing=missing,
            installed=sorted(self.available_names()),
        )

    @staticmethod
    def _find_context_length(
        model_info: dict[str, Any],
    ) -> tuple[int | None, str | None]:
        """
        Find the architecture-specific context length.

        Example:
            qwen3.context_length
            llama.context_length
            gemma.context_length

        Returns the value together with the model_info key it was
        found under, so callers can tell a real match from a fallback.
        """

        # Preferred approach: architecture-specific field.
        for key, value in model_info.items():
            if key.endswith(".context_length") and isinstance(value, int):
                return value, key

        # Defensive fallbacks.
        for key in (
            "context_length",
            "llama.context_length",
            "qwen.context_length",
            "qwen2.context_length",
            "qwen3.context_length",
        ):
            value = model_info.get(key)

            if isinstance(value, int):
                return value, key

        return None, None

    @staticmethod
    def _find_int(
        model_info: dict[str, Any],
        suffix: str,
    ) -> int | None:
        """Find an architecture-prefixed int key, e.g. 'qwen.block_count'."""

        for key, value in model_info.items():
            if key.endswith(suffix) and isinstance(value, int):
                return value
        return None

    @staticmethod
    def _find_string(
        model_info: dict[str, Any],
        key: str,
    ) -> str | None:

        value = model_info.get(key)

        if value is None:
            return None

        if isinstance(value, str):
            return value

        return str(value)
