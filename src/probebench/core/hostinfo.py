"""Hardware provenance for a run (D-013).

Two blocks, because they answer different questions. `machine` is what
computer this was; `snapshot` is what it had spare when the run started.

The load-bearing rule is that this describes the machine running THIS
process. When OLLAMA_HOST points elsewhere, inference happened on a computer
we cannot see, and reporting the client's specs would be worse than reporting
nothing - it would look authoritative and be grouped on. See LIMITATIONS 1.16.
"""

import os
import platform
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

from probebench.core.preflight import (
    available_ram_bytes,
    available_vram_bytes,
    swap_total_bytes,
    total_ram_bytes,
)

_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def is_local_host(host: str) -> bool:
    """Whether an Ollama endpoint refers to this machine."""

    hostname = urlparse(host).hostname

    return (hostname or "") in _LOCAL_HOSTNAMES


def collect_host_info(ollama_host: str) -> dict[str, Any]:
    """Hardware provenance for the record's `host` block."""

    local = is_local_host(ollama_host)

    return {
        "ollama_host": ollama_host,
        # "remote" is not a failure to detect - it is the honest statement
        # that the machine which ran inference is not this one and cannot be
        # inspected. Ollama's API exposes no server hardware.
        "machine_source": "local" if local else "remote",
        "machine": _machine() if local else None,
        "snapshot": _snapshot() if local else None,
    }


def _machine() -> dict[str, Any]:
    """Static facts about this computer. None means "not detected"."""

    gpus = _nvidia_gpus()

    return {
        "platform": platform.system(),
        "release": platform.release(),
        "machine_arch": platform.machine(),
        "cpu_model": _cpu_model(),
        "cpu_cores_physical": _physical_cores(),
        "cpu_cores_logical": os.cpu_count(),
        "ram_total_bytes": total_ram_bytes(),
        "swap_total_bytes": swap_total_bytes(),
        # Empty list means "looked and found none"; it is indistinguishable
        # from "could not look" on a non-NVIDIA or non-Linux host, which is
        # why `platform` above is recorded (LIMITATIONS 2.3, 2.4).
        "gpus": gpus,
        "gpu_driver_version": gpus[0]["driver_version"] if gpus else None,
    }


def _snapshot() -> dict[str, Any]:
    """What the machine had spare at run start.

    Taken once, not per case: an nvidia-smi subprocess per case would be 330
    of them in a sweep the size of J-011's, to measure something that mostly
    does not move. Contention DURING a run is therefore unmeasured.
    """

    return {
        "ram_available_bytes": available_ram_bytes(),
        "vram_free_bytes": available_vram_bytes(),
    }


def _cpu_model() -> str | None:
    """CPU model string, Linux only."""

    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (OSError, IndexError):
        return None

    return None


def _physical_cores() -> int | None:
    """Physical core count, Linux only.

    Distinct from os.cpu_count(): llama.cpp thread counts and memory bandwidth
    track physical cores, while SMT siblings inflate the logical count, so a
    latency comparison wants both.
    """

    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("cpu cores"):
                    return int(line.split(":", 1)[1].strip())
    except (OSError, ValueError, IndexError):
        return None

    return None


def _nvidia_gpus() -> list[dict[str, Any]]:
    """Name, total VRAM and driver for each visible NVIDIA GPU.

    One nvidia-smi call for all three fields rather than three calls, since
    each costs on the order of 100ms and this runs on the startup path.
    """

    if shutil.which("nvidia-smi") is None:
        return []

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    gpus: list[dict[str, Any]] = []

    for line in completed.stdout.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]

        if len(parts) != 3:
            continue

        name, total_mib, driver = parts

        gpus.append(
            {
                "name": name,
                "vram_total_bytes": int(total_mib) * 1024 * 1024 if total_mib.isdigit() else None,
                "driver_version": driver,
            }
        )

    return gpus
