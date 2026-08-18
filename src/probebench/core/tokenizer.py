from abc import ABC, abstractmethod

class Tokenizer(ABC):

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        raise NotImplementedError

    def count(self, text: str) -> int:
        return len(self.encode(text))