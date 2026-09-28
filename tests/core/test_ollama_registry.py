import pytest

from probebench.models.registry import (
    OllamaModelRegistry,
)


@pytest.mark.integration
def test_qwen_model_inspection() -> None:

    registry = OllamaModelRegistry()

    info = registry.inspect("qwen3:4b")

    assert info.name == "qwen3:4b"

    assert info.family is not None

    assert info.context_length is not None
    assert info.context_length > 0

    assert info.capabilities
