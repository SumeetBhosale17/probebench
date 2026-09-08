from probebench.core.kvprobe import (
    KV_TYPES,
    TOLERANCE,
    KvProbeResult,
    classify,
    probe_kv_precision,
)

# qwen3:0.6b - 28 layers, 8 KV heads, head_dim 128.
DIVISOR = 2 * 28 * 8 * 128


class FakeClient:
    """Reports sizes consistent with a chosen bytes-per-element."""

    def __init__(self, bytes_per_element: float, weights: int = 500_000_000) -> None:
        self.bytes_per_element = bytes_per_element
        self.weights = weights
        self.loaded: dict[str, object] = {}

    def chat(self, *, model: str, options: dict, **_: object) -> dict:
        self.loaded = {"model": model, "context_length": options["num_ctx"]}
        return {"message": {"content": "ok"}}

    def ps(self) -> dict:
        ctx = int(self.loaded["context_length"])  # type: ignore[call-overload]
        size = self.weights + int(DIVISOR * self.bytes_per_element * ctx)
        return {"models": [{**self.loaded, "size": size}]}


def test_classify_recognises_known_precisions() -> None:
    for name, value in KV_TYPES.items():
        assert classify(value) == name


def test_classify_accepts_both_observed_modes() -> None:
    """The probe reads BIMODALLY, not noisily (J-026).

    Repeated probes of one unchanged server return two discrete values ~16%
    apart, bracketing the true constant. Every one of these was measured.
    """

    # f16, observed J-018 and J-022.
    assert classify(1.932) == "f16"
    assert classify(2.080) == "f16"

    # q8_0, observed J-026. 1.1935 was classified None before the constants
    # were corrected from nominal bit-widths to ggml's block sizes.
    assert classify(1.0315) == "q8_0"
    assert classify(1.1935) == "q8_0"


def test_kv_types_use_ggml_block_sizes_not_nominal_bit_widths() -> None:
    """A q8_0 block is 32 values plus a 2-byte scale, so 34/32 (J-026)."""

    assert KV_TYPES["q8_0"] == 34 / 32
    assert KV_TYPES["q4_0"] == 18 / 32
    assert KV_TYPES["f16"] == 2.0


def test_the_bands_cannot_overlap() -> None:
    """Two classes matching one measurement would make classification meaningless."""

    bands = [
        (name, centre * (1 - TOLERANCE), centre * (1 + TOLERANCE))
        for name, centre in KV_TYPES.items()
    ]

    for i, (_, low_a, high_a) in enumerate(bands):
        for _, low_b, high_b in bands[i + 1 :]:
            assert high_b < low_a or high_a < low_b


def test_classify_returns_none_for_an_unrecognised_value() -> None:
    """An unknown precision is data, not something to snap to the nearest class."""

    assert classify(1.5) is None


def test_probe_recovers_f16() -> None:
    result = probe_kv_precision(FakeClient(2.0), "m", DIVISOR)

    assert result.measured
    assert result.kv_type == "f16"
    assert abs((result.bytes_per_element or 0) - 2.0) < 0.01


def test_probe_recovers_q8_0_and_is_weight_independent() -> None:
    """Differencing cancels weights, so the answer must not depend on them."""

    small = probe_kv_precision(FakeClient(1.0, weights=1), "m", DIVISOR)
    large = probe_kv_precision(FakeClient(1.0, weights=9_000_000_000), "m", DIVISOR)

    assert small.kv_type == "q8_0"
    assert large.kv_type == "q8_0"
    assert abs((small.bytes_per_element or 0) - (large.bytes_per_element or 0)) < 1e-6


def test_probe_without_geometry_is_unavailable_not_wrong() -> None:
    result = probe_kv_precision(FakeClient(2.0), "m", None)

    assert not result.measured
    assert result.reason is not None
    assert result.to_metadata()["kv_cache_probe"].startswith("unavailable")


def test_probe_refuses_too_small_a_context_separation() -> None:
    result = probe_kv_precision(FakeClient(2.0), "m", DIVISOR, small_ctx=4096, large_ctx=8192)

    assert not result.measured


def test_unavailable_result_records_no_measurement() -> None:
    """Invariant 8 applied to the probe: absent, never defaulted."""

    metadata = KvProbeResult(None, None, reason="nope").to_metadata()

    assert metadata["kv_cache_bytes_per_element_measured"] is None
    assert metadata["kv_cache_type_effective"] is None
    assert metadata["kv_cache_probe_evidence"] is None


def test_an_unrecognised_measurement_is_not_reported_as_verified() -> None:
    """ "measured" must not cover "measured and not understood" (J-026)."""

    recognised = probe_kv_precision(FakeClient(2.0), "m", DIVISOR).to_metadata()
    assert recognised["kv_cache_probe"] == "measured"

    # 1.5 sits between q8_0 and f16 and matches nothing.
    unrecognised = probe_kv_precision(FakeClient(1.5), "m", DIVISOR).to_metadata()
    assert unrecognised["kv_cache_type_effective"] is None
    assert unrecognised["kv_cache_probe"] == "measured_unrecognised"
