import tiktoken

from probebench.core.tokenizer import Tokenizer


class TiktokenTokenizer(Tokenizer):
    """Tokenizer backed by tiktoken."""

    def __init__(self, encoding_name: str) -> None:
        self.encoding_name = encoding_name
        self._encoding = tiktoken.get_encoding(encoding_name)

    def encode(self, text: str) -> list[int]:
        return self._encoding.encode(text)

    def decode(self, tokens: list[int]) -> str:
        return self._encoding.decode(tokens)
