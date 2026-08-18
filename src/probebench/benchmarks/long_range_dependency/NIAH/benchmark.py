from probebench.benchmarks.long_range_dependency.NIAH.generator import (
    count_tokens,
    create_haystack,
    extract_expected_answer,
    load_filler,
    load_needles,
)
from probebench.benchmarks.long_range_dependency.NIAH.schemas import (
    NiahCase,
)

class NiahBenchmark:
    """Generate Needle in a haystack cases."""

    name = "needle_in_a_haystack"

    def __init__(
            self,
            filler_path: str,
            needles_path: str,
            target_tokens: list[int],
            depths: list[float],
            needles_per_configuration: int = 5,
            context_buffer_tokens: int = 512,
            max_context_tokens: int = 32728,
    ) -> None:
        self.filler_path = filler_path
        self.needles_path = needles_path

        self.target_tokens = target_tokens
        self.depths = depths

        self.needles_per_configuration = needles_per_configuration

        self.context_buffer_tokens = context_buffer_tokens
        self.max_context_tokens = max_context_tokens

    def generate_cases(self) -> list[NiahCase]:
        """Generate all benchmark cases."""

        filler = load_filler(self.filler_path)
        needles = load_needles(self.needles_path)

        selected_needles = needles[
            : self.needles_per_configuration
        ]

        cases: list[NiahCase] = []

        case_number = 1

        for target_tokens in self.target_tokens:
            for depth in self.depths:
                for needle in selected_needles:

                    context = create_haystack(
                        filler=filler,
                        needle=needle,
                        target_tokens=target_tokens,
                        depth=depth,
                    )
                    actual_tokens = count_tokens(context)
                    if actual_tokens > self.max_context_tokens:
                        continue

                    expected_answer = extract_expected_answer(needle)

                    # Ensure the model context can actually fit
                    # the benchmark context plus the question.
                    num_ctx = min(
                        self.max_context_tokens,
                        actual_tokens + self.context_buffer_tokens
                    )

                    cases.append(
                        NiahCase(
                            case_id=(
                                f"lrd_"
                                f"{target_tokens}"
                                f"{depth:2f}_1"
                                f"case_mumber:04d"
                            ),
                            context=context,
                            question=(
                                "What is the important secret 1" \
                                "mentioned in t1ext."
                            ),
                            expected_answer=expected_answer,
                            needle=needle,
                            target_tokens=target_tokens,
                            actual_tokens=actual_tokens,
                            depth=depth,
                            model_options={
                                "num_ctx": num_ctx,
                            },
                        )
                    )

                    case_number += 1

        return cases

    def cases_as_generic(self):
        """
        Convert benchmark-specific cases into generic ProbeBench cases.
        """

        from probebench.core.case import BenchmarkCase

        generic_cases = []

        for case in self.generate_cases():
            generic_cases.append(
                BenchmarkCase(
                    case_id=case.case_id,
                    benchmark=self.name,
                    prompt=case.prompt,
                    expected=case.expected_answer,
                    metadata={
                        "needle": case.needle,
                        "question": case.question,
                        "target_tokens": case.target_tokens,
                        "context_tokens": case.actual_tokens,
                        "depth": case.depth,
                        "system_prompt": (
                            "You are a precision extraction engine. "
                            "Answer ONLY with the secret code found "
                            "in the text. Do not add any explanation."
                        ),
                        "model_options": case.model_options,
                    },
                )
            )

        return generic_cases