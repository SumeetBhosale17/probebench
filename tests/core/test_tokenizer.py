from probebench.tokenizers.tiktoken import TiktokenTokenizer

def test_tiktoken_tokenizer() -> None:
    tokenizer = TiktokenTokenizer(
        "cl100k_base"
    )

    tokens = tokenizer.encode(
        "Hello ProbeBench"
    )

    assert len(tokens) > 0
    assert tokenizer.count(
        "Hello ProbeBench"
    ) == len(tokens)