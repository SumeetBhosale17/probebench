from probebench.benchmarks.long_range_dependency.NIAH.benchmark import NiahBenchmark
from probebench.benchmarks.long_range_dependency.NIAH.settings import NiahParams


def test_defaults_match_the_hardcoded_values_byte_for_byte() -> None:
    """If these drift, every archived case_fingerprint stops matching a fresh run.

    NiahParams exists to make these configurable; its defaults must therefore
    reproduce exactly what the class attributes said before it existed.
    """

    params = NiahParams()

    assert params.question == NiahBenchmark.question
    assert params.system_prompt == NiahBenchmark.system_prompt


def test_a_typo_in_a_niah_knob_raises() -> None:
    import pytest
    from pydantic import ValidationError

    # Unpacked from a dict so the static checker cannot object to the typo
    # this test exists to prove is caught at RUNTIME.
    with pytest.raises(ValidationError):
        NiahParams(**{"fillerpath": "x.txt"})
