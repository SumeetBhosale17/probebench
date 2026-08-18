from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ModelResponse:
    """Response returned by a model provider."""

    text: str
    latency_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)

class Model(ABC):
    """Interface implemented by model providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **options: Any
    ) -> ModelResponse:
        """Generate a response for a prompt"""
        raise NotImplementedError