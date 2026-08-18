import tiktoken

from probebench.core.tokenizer import Tokenizer

class TiktokenTokenizer(Tokenizer):
    def __init__(self, encoding_name: str) -> None:
        self.encoding_name = encoding_name
        self.encoding = tiktoken.get_encoding(
            encoding_name
        )

    def encode(self, text: str) -> list[int]:
        return self.encoding.encode(text)