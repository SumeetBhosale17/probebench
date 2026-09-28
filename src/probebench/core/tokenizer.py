from abc import ABC, abstractmethod


class Tokenizer(ABC):
    """Tokenizer used by a benchmark."""

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """Encode text into token IDs."""
        raise NotImplementedError

    @abstractmethod
    def decode(self, tokens: list[int]) -> str:
        """Decode token IDs into text."""
        raise NotImplementedError

    def count(self, text: str) -> int:
        """Return token count."""
        return len(self.encode(text))
