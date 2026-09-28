from probebench.tokenizers.tiktoken import (
    TiktokenTokenizer,
)


def test_tiktoken_tokenizer() -> None:

    tokenizer = TiktokenTokenizer("cl100k_base")

    text = "Hello ProbeBench"

    tokens = tokenizer.encode(text)

    assert len(tokens) > 0

    assert tokenizer.count(text) == len(tokens)

    decoded = tokenizer.decode(tokens)

    assert decoded == text
