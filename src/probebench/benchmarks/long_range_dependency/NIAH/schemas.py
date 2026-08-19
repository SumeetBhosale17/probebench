from dataclasses import dataclass


@dataclass
class NiahCase:
    """Input defining one long-range dependency experiment."""

    case_id: str
    context: str
    question: str

    expected_answer: str
    needle: str

    target_tokens: int
    actual_tokens: int
    depth: float

    model_options: dict

    @property
    def prompt(self) -> str:
        return f"{self.context}\n\nQuestion: {self.question}"
