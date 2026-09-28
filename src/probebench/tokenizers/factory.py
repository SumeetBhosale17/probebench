from probebench.core.config import TokenizerConfig
from probebench.core.tokenizer import Tokenizer
from probebench.tokenizers.tiktoken import (
    TiktokenTokenizer,
)


def create_tokenizer(
    config: TokenizerConfig,
) -> Tokenizer:

    if config.provider == "tiktoken":
        return TiktokenTokenizer(encoding_name=config.name)

    raise ValueError(f"Unsupported tokenizer provider: {config.provider}")
