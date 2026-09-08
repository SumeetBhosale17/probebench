"""Measure the server's KV cache precision instead of trusting a flag (D-017).

ProbeBench is an HTTP client of the Ollama daemon. On a default install that
daemon is a systemd service running as its own user, so its environment - where
OLLAMA_KV_CACHE_TYPE actually lives - is neither ours nor readable (J-018).
Asking our own shell what the server is doing answers a question about the
wrong process.

So measure it. `/api/ps` reports each loaded model's `size` and the
`context_length` it was loaded at. `size` is

    weights + compute buffers + kv_bytes_per_token * num_ctx

and only the last term depends on context, so loading the same model twice at
different context sizes and differencing cancels everything else exactly:

    kv_bytes_per_token = (size_b - size_a) / (ctx_b - ctx_a)
    bytes_per_element  = kv_bytes_per_token / (2 * n_layers * n_kv_heads * head_dim)

This uses R-001's validated KV arithmetic as a measuring instrument rather than
as a predictor. It works remotely, against a service-managed daemon, and on a
machine somebody else configured - which is where most of this project's
compute is going to run.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Context sizes to load at. The delta must be large enough that the KV term
# dominates the noise: at 12,288 tokens of separation the measured error was
# 3.4% (J-018), which is comfortable against hypotheses that are 2x apart.
DEFAULT_SMALL_CTX = 4_096
DEFAULT_LARGE_CTX = 16_384

# Minimum separation before a measurement is trusted at all. Below this the
# per-context overhead that causes the 3.4% residual is no longer small
# relative to the signal.
MIN_CTX_DELTA = 8_192

# Known KV element sizes, in bytes.
#
# NOT nominal bit-widths. ggml quantises in blocks of 32 values plus one fp16
# scale, so a "1 byte" element actually costs 34/32 bytes (J-026):
#
#     q8_0:  (32 x 1   + 2) / 32 = 1.0625
#     q4_0:  (32 x 0.5 + 2) / 32 = 0.5625
#     f16:                         2.0
#
# Using 1.0 for q8_0 put the acceptance window off-centre and rejected a
# correct reading of 1.19 as unrecognised.
KV_TYPES: dict[str, float] = {
    "f16": 2.0,
    "q8_0": 34 / 32,
    "q4_0": 18 / 32,
}

# Classification band. The probe reads BIMODALLY rather than noisily: repeated
# probes of one unchanged server return two discrete values about 16% apart
# (J-026), bracketing the true constant. 15% around the correct centres accepts
# both modes for every type, and the bands still cannot overlap because the
# types are ~2x apart:
#
#     f16   [1.700, 2.300]
#     q8_0  [0.903, 1.222]
#     q4_0  [0.478, 0.647]
#
# A measurement outside every band is recorded raw and classified None - an
# unrecognised precision is data, not a rounding problem (D-017).
TOLERANCE = 0.15


@dataclass(frozen=True)
class KvProbeResult:
    """What the server was measured to be doing, and how confident that is."""

    # None when the probe could not run; `reason` then says why.
    bytes_per_element: float | None
    kv_type: str | None
    reason: str | None = None

    # Raw evidence, so the classification can be re-derived offline without
    # re-running the probe.
    small_ctx: int | None = None
    large_ctx: int | None = None
    small_size_bytes: int | None = None
    large_size_bytes: int | None = None

    @property
    def measured(self) -> bool:
        return self.bytes_per_element is not None

    def to_metadata(self) -> dict[str, Any]:
        """The `generation` fields describing KV precision."""

        return {
            "kv_cache_bytes_per_element_measured": self.bytes_per_element,
            "kv_cache_type_effective": self.kv_type,
            # Three states, not two. An unrecognised measurement is neither a
            # verification nor a failure to measure, and calling it "measured"
            # overstated the confidence (J-026).
            "kv_cache_probe": (
                "measured"
                if self.kv_type is not None
                else "measured_unrecognised"
                if self.measured
                else f"unavailable: {self.reason}"
            ),
            "kv_cache_probe_evidence": {
                "small_ctx": self.small_ctx,
                "large_ctx": self.large_ctx,
                "small_size_bytes": self.small_size_bytes,
                "large_size_bytes": self.large_size_bytes,
            }
            if self.measured
            else None,
        }


class _PsClient(Protocol):
    """The slice of the Ollama client this module needs."""

    def chat(self, *args: Any, **kwargs: Any) -> Any: ...

    def ps(self) -> Any: ...


def classify(bytes_per_element: float) -> str | None:
    """Name a measured element size, or None if it matches nothing known."""

    for name, expected in KV_TYPES.items():
        if abs(bytes_per_element - expected) <= TOLERANCE * expected:
            return name

    return None


def probe_kv_precision(
    client: _PsClient,
    model_name: str,
    kv_geometry_divisor: int | None,
    small_ctx: int = DEFAULT_SMALL_CTX,
    large_ctx: int = DEFAULT_LARGE_CTX,
    settle_seconds: float = 1.5,
) -> KvProbeResult:
    """Measure bytes-per-element of the server's KV cache.

    `kv_geometry_divisor` is `2 * n_layers * n_kv_heads * head_dim` from GGUF
    metadata. It is passed in rather than derived here so this module stays
    free of model-registry concerns and is trivially testable.
    """

    if not kv_geometry_divisor:
        return KvProbeResult(None, None, reason="KV geometry unknown for this model")

    if large_ctx - small_ctx < MIN_CTX_DELTA:
        return KvProbeResult(
            None,
            None,
            reason=f"context separation {large_ctx - small_ctx} below minimum {MIN_CTX_DELTA}",
        )

    try:
        small_size = _load_and_measure(client, model_name, small_ctx, settle_seconds)
        large_size = _load_and_measure(client, model_name, large_ctx, settle_seconds)
    except Exception as exc:  # noqa: BLE001 - a failed probe is missing data, not a failed run
        return KvProbeResult(None, None, reason=f"{type(exc).__name__}: {exc}")

    if small_size is None or large_size is None:
        return KvProbeResult(
            None,
            None,
            reason="server did not report a size for the loaded model",
            small_ctx=small_ctx,
            large_ctx=large_ctx,
        )

    per_token = (large_size - small_size) / (large_ctx - small_ctx)

    if per_token <= 0:
        # Non-monotonic size means something other than KV moved between the
        # two loads - another model was evicted, or the server reused a runner.
        return KvProbeResult(
            None,
            None,
            reason=f"size did not grow with context ({small_size} -> {large_size})",
            small_ctx=small_ctx,
            large_ctx=large_ctx,
            small_size_bytes=small_size,
            large_size_bytes=large_size,
        )

    bytes_per_element = per_token / kv_geometry_divisor

    return KvProbeResult(
        bytes_per_element=bytes_per_element,
        kv_type=classify(bytes_per_element),
        small_ctx=small_ctx,
        large_ctx=large_ctx,
        small_size_bytes=small_size,
        large_size_bytes=large_size,
    )


def _load_and_measure(
    client: _PsClient,
    model_name: str,
    num_ctx: int,
    settle_seconds: float,
) -> int | None:
    """Load the model at num_ctx and read back its resident size."""

    # num_predict=1 so we pay for a load and one token, not a generation. The
    # short keep_alive matters: the probe must not hold a runner open at a
    # num_ctx the run does not use, which would defeat invariant 3's whole
    # purpose of keeping one runner for the sweep.
    client.chat(
        model=model_name,
        messages=[{"role": "user", "content": "probe"}],
        options={"num_ctx": num_ctx, "num_predict": 1, "temperature": 0},
        keep_alive="60s",
    )

    # `ps` can lag the chat response by a moment on a loaded machine.
    time.sleep(settle_seconds)

    for entry in _ps_models(client):
        if entry.get("model") != model_name:
            continue

        # Ollama may still list a previous load of the same model at a
        # different context; match on the context we asked for so the two
        # measurements cannot come from the same runner.
        if entry.get("context_length") == num_ctx:
            return entry.get("size")

    return None


def _ps_models(client: _PsClient) -> list[dict[str, Any]]:
    """Normalise `ps()` across ollama-python's dict and pydantic returns."""

    response = client.ps()

    if hasattr(response, "model_dump"):
        response = response.model_dump()

    models = response.get("models") if isinstance(response, dict) else None

    if not models:
        return []

    return [entry.model_dump() if hasattr(entry, "model_dump") else entry for entry in models]
