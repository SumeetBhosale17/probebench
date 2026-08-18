from dataclasses import dataclass
from typing import Any

import ollama


@dataclass
class ModelInfo:
    """Normalized information about an Ollama model."""

    name: str

    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None

    context_length: int | None = None

    capabilities: list[str] | None = None

    tokenizer_model: str | None = None
    tokenizer_pre: str | None = None

    raw: dict[str, Any] | None = None


class OllamaModelRegistry:
    """Discover and inspect models available to Ollama."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
    ) -> None:
        self.client = ollama.Client(host=host)

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

        model_info = dict(
            response.modelinfo or {}
        )

        capabilities = [
            str(capability)
            for capability in (
                response.capabilities or []
            )
        ]

        context_length = self._find_context_length(
            model_info
        )

        tokenizer_model = self._find_string(
            model_info,
            "tokenizer.ggml.model",
        )

        tokenizer_pre = self._find_string(
            model_info,
            "tokenizer.ggml.pre",
        )

        raw = {
            "details": (
                details.model_dump()
                if details is not None
                else {}
            ),
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
            capabilities=capabilities,
            tokenizer_model=tokenizer_model,
            tokenizer_pre=tokenizer_pre,
            raw=raw,
        )

    @staticmethod
    def _find_context_length(
        model_info: dict[str, Any],
    ) -> int | None:
        """
        Find the architecture-specific context length.

        Example:
            qwen3.context_length
            llama.context_length
            gemma.context_length
        """

        # Preferred approach: architecture-specific field.
        for key, value in model_info.items():

            if key.endswith(
                ".context_length"
            ):
                if isinstance(value, int):
                    return value

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