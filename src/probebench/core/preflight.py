import logging
import shutil
import subprocess
from dataclasses import dataclass

from probebench.models.registry import ModelInfo

logger = logging.getLogger(__name__)

GIB = 1024**3


@dataclass
class MemoryPlanRow:
    """One planned context size and whether this machine can afford it."""

    num_ctx: int
    weights_bytes: int
    kv_bytes: int
    required_bytes: int
    budget_bytes: int
    fits: bool

    @property
    def headroom_bytes(self) -> int:
        return self.budget_bytes - self.required_bytes


def total_ram_bytes() -> int | None:
    """Total installed RAM, for reporting rather than budgeting."""

    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None

    return None


def swap_total_bytes() -> int | None:
    """Total swap. Zero swap turns memory pressure into hard allocation failures."""

    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("SwapTotal:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None

    return None


def available_ram_bytes() -> int | None:
    """Bytes of RAM the kernel says are available right now."""

    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None

    return None


def gpu_names() -> list[str]:
    """Names of visible NVIDIA GPUs, for the health report."""

    if shutil.which("nvidia-smi") is None:
        return []

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    return [line.strip() for line in completed.stdout.strip().splitlines() if line.strip()]


def available_vram_bytes() -> int | None:
    """Free VRAM summed across NVIDIA GPUs, or None when Unknown."""

    if shutil.which("nvidia-smi") is None:
        return None

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    total = 0

    for line in completed.stdout.strip().splitlines():
        value = line.strip()
        if value.isdigit():
            total += int(value) * 1024 * 1024

    return total or None


def estimate_case_bytes(
    model_info: ModelInfo,
    num_ctx: int,
    bytes_per_element: int = 2,
) -> int | None:
    """Weights + KV cache + llama.cpp compute buffer for one case."""

    kv_bytes = model_info.kv_cache_bytes(num_ctx, bytes_per_element)

    if kv_bytes is None or model_info.size_bytes is None:
        return None

    # llama.cpp also allocates a compute buffer; ~10% of KV cache is a workable guess.
    return model_info.size_bytes + kv_bytes + int(kv_bytes * 0.10)


def check_memory_budget(
    model_info: ModelInfo,
    num_ctx: int,
    *,
    headroom_fraction: float = 0.85,
    bytes_per_element: int = 2,
) -> tuple[bool, str]:
    """Return (fits, human-readable explanation). Never raises."""

    required = estimate_case_bytes(model_info, num_ctx, bytes_per_element)

    if required is None:
        return True, f"num_ctx={num_ctx:,}: KV geometry unknown, preflight skipped."

    ram = available_ram_bytes() or 0
    vram = available_vram_bytes() or 0

    budget = int((ram + vram) * headroom_fraction)

    kv_bytes = model_info.kv_cache_bytes(num_ctx, bytes_per_element) or 0

    message = (
        f"num_ctx={num_ctx:,} needs ~{required / GIB:.1f} GiB "
        f"(weights {(model_info.size_bytes or 0) / GIB:.1f} + "
        f"KV {kv_bytes / GIB:.1f}); "
        f"budget ~{budget / GIB:.1f} GiB "
        f"(RAM {ram / GIB:.1f} + VRAM {vram / GIB:.1f} @ {headroom_fraction:.0%})"
    )

    return required <= budget, message


def memory_budget_bytes(headroom_fraction: float = 0.85) -> int:
    """Bytes this machine can spend on a model right now."""

    ram = available_ram_bytes() or 0
    vram = available_vram_bytes() or 0

    return int((ram + vram) * headroom_fraction)


def max_feasible_num_ctx(
    model_info: ModelInfo,
    *,
    headroom_fraction: float = 0.85,
    bytes_per_element: int = 2,
) -> int | None:
    """Largest context this machine can hold for this model, or None if unknown.

    Solves the budget equation directly rather than searching:
        weights + 1.1 * kv_per_token * num_ctx <= budget
    """

    per_token = model_info.kv_bytes_per_token(bytes_per_element)

    if per_token is None or model_info.size_bytes is None:
        return None

    budget = memory_budget_bytes(headroom_fraction)

    spare = budget - model_info.size_bytes

    if spare <= 0:
        return 0

    # The 1.1 mirrors the compute-buffer allowance in estimate_case_bytes.
    feasible = int(spare / (per_token * 1.10))

    if model_info.context_length is not None:
        feasible = min(feasible, model_info.context_length)

    return max(feasible, 0)


def recommend_target_tokens(
    model_info: ModelInfo,
    *,
    headroom_fraction: float = 0.85,
    bytes_per_element: int = 2,
    context_buffer_tokens: int = 512,
    ladder: tuple[int, ...] = (
        4_000,
        8_000,
        16_000,
        32_000,
        64_000,
        128_000,
        256_000,
    ),
) -> list[int]:
    """Pick the sweep this machine can actually finish.

    Returns every rung of the ladder that fits in memory. A NIAH curve needs
    several context lengths to be meaningful, so this keeps all feasible
    rungs rather than only the largest one.
    """

    ceiling = max_feasible_num_ctx(
        model_info,
        headroom_fraction=headroom_fraction,
        bytes_per_element=bytes_per_element,
    )

    if ceiling is None:
        # Geometry unknown: fall back to a conservative sweep.
        return [4_000, 8_000, 16_000]

    feasible = [rung for rung in ladder if rung + context_buffer_tokens <= ceiling]

    return feasible or [ladder[0]]


def build_memory_plan(
    model_info: ModelInfo,
    num_ctx_values: list[int],
    *,
    headroom_fraction: float = 0.85,
    bytes_per_element: int = 2,
) -> list[MemoryPlanRow]:
    """Per-context-size feasibility rows, for printing or enforcement."""

    budget = memory_budget_bytes(headroom_fraction)
    weights = model_info.size_bytes or 0

    rows: list[MemoryPlanRow] = []

    for num_ctx in sorted(set(num_ctx_values)):
        kv_bytes = model_info.kv_cache_bytes(num_ctx, bytes_per_element) or 0
        required = estimate_case_bytes(model_info, num_ctx, bytes_per_element)

        if required is None:
            continue

        rows.append(
            MemoryPlanRow(
                num_ctx=num_ctx,
                weights_bytes=weights,
                kv_bytes=kv_bytes,
                required_bytes=required,
                budget_bytes=budget,
                fits=required <= budget,
            )
        )

    return rows


def format_memory_plan(rows: list[MemoryPlanRow]) -> str:
    """Render a memory plan as an aligned text table."""

    if not rows:
        return "  (KV geometry unavailable for this model - cannot estimate memory.)"

    lines = [
        f"  {'context':>10}  {'weights':>9}  {'KV cache':>9}  {'total':>9}  {'budget':>9}  verdict",
        f"  {'-' * 10}  {'-' * 9}  {'-' * 9}  {'-' * 9}  {'-' * 9}  {'-' * 7}",
    ]

    for row in rows:
        lines.append(
            f"  {row.num_ctx:>10,}  "
            f"{row.weights_bytes / GIB:>8.1f}G  "
            f"{row.kv_bytes / GIB:>8.1f}G  "
            f"{row.required_bytes / GIB:>8.1f}G  "
            f"{row.budget_bytes / GIB:>8.1f}G  "
            f"{'OK' if row.fits else 'TOO LARGE'}"
        )

    return "\n".join(lines)
