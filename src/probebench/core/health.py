"""Pre-run environment checks.

Everything here runs before a single token is generated. The goal is that a
run either starts and finishes, or fails in the first second with a message
that says exactly what to fix - rather than dying at case 3 of 20.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from probebench.core.preflight import (
    GIB,
    available_ram_bytes,
    available_vram_bytes,
    gpu_names,
    swap_total_bytes,
    total_ram_bytes,
)
from probebench.models.host import default_ollama_host
from probebench.models.registry import OllamaModelRegistry

OK = "ok"
WARN = "warn"
FAIL = "fail"

_SYMBOLS = {OK: "[ok]  ", WARN: "[warn]", FAIL: "[FAIL]"}


@dataclass
class CheckResult:
    """Outcome of one environment check."""

    name: str
    status: str
    detail: str
    remedy: str | None = None


@dataclass
class HealthReport:
    """All checks from one health run."""

    checks: list[CheckResult] = field(default_factory=list)

    # Models that are simply not installed. Held separately so the caller can
    # offer to pull them instead of only reporting the failure.
    missing_models: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[CheckResult]:
        return [check for check in self.checks if check.status == FAIL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [check for check in self.checks if check.status == WARN]

    @property
    def ok(self) -> bool:
        return not self.failed

    def render(self) -> str:
        lines = ["ProbeBench Health Check", "=" * 60]

        for check in self.checks:
            lines.append(f"{_SYMBOLS[check.status]} {check.name}: {check.detail}")

            if check.remedy and check.status != OK:
                lines.append(f"        -> {check.remedy}")

        lines.append("")

        if self.failed:
            lines.append(f"{len(self.failed)} check(s) failed.")
        elif self.warnings:
            lines.append(f"All required checks passed ({len(self.warnings)} warning(s)).")
        else:
            lines.append("All checks passed.")

        return "\n".join(lines)


def check_ollama(host: str | None = None) -> tuple[CheckResult, list[str]]:
    """Confirm the Ollama daemon answers, and list what it has installed."""

    host = host or default_ollama_host()

    registry = OllamaModelRegistry(host=host)

    try:
        models = registry.list_models()
    except Exception as exc:  # noqa: BLE001 - any transport failure is a fail
        return (
            CheckResult(
                name="Ollama daemon",
                status=FAIL,
                detail=f"cannot reach {host}: {exc}",
                remedy="Start it with `ollama serve`, or set OLLAMA_HOST if it is elsewhere.",
            ),
            [],
        )

    names = sorted(model.name for model in models)

    if not names:
        return (
            CheckResult(
                name="Ollama daemon",
                status=WARN,
                detail=f"reachable at {host} but no models are installed",
                remedy="Install one with `ollama pull qwen3:4b`.",
            ),
            names,
        )

    return (
        CheckResult(
            name="Ollama daemon",
            status=OK,
            detail=f"reachable at {host}, {len(names)} model(s) installed",
        ),
        names,
    )


def _systemd_ollama_models() -> str | None:
    """OLLAMA_MODELS as declared by the systemd unit, if there is one.

    Distributions disagree about where the service keeps its models
    (/var/lib/ollama on Arch, /usr/share/ollama/.ollama on Debian), so ask
    the unit rather than guessing.
    """

    if shutil.which("systemctl") is None:
        return None

    try:
        completed = subprocess.run(
            ["systemctl", "show", "ollama", "--property=Environment"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    for token in completed.stdout.strip().split():
        if token.startswith("OLLAMA_MODELS="):
            return token.split("=", 1)[1]

    return None


def _store_candidates() -> list[Path]:
    """Every plausible Ollama model store on this machine."""

    candidates = [
        Path.home() / ".ollama" / "models",
        Path("/usr/share/ollama/.ollama/models"),
        Path("/var/lib/ollama/models"),
        Path("/var/lib/ollama"),
    ]

    systemd_store = _systemd_ollama_models()

    if systemd_store:
        candidates.insert(0, Path(systemd_store))

    found: list[Path] = []

    for candidate in candidates:
        # A store is identified by its manifests directory, which may sit
        # either at <root>/manifests or <root>/models/manifests.
        if (candidate / "manifests").is_dir() or (candidate / "models" / "manifests").is_dir():
            resolved = candidate.resolve()

            if resolved not in found:
                found.append(resolved)

    return found


def check_model_store() -> CheckResult:
    """Warn when two Ollama model stores exist on this machine.

    A systemd `ollama` service and a user-launched `ollama serve` use
    different directories and both bind :11434. If the active server changes
    mid-run, a model that was resolving fine starts returning 404.
    """

    override = os.environ.get("OLLAMA_MODELS")

    if override:
        return CheckResult(
            name="Model store",
            status=OK,
            detail=f"OLLAMA_MODELS is set explicitly: {override}",
        )

    present = _store_candidates()

    if len(present) > 1:
        return CheckResult(
            name="Model store",
            status=WARN,
            detail="two model stores exist: " + ", ".join(str(store) for store in present),
            remedy=(
                "Whichever `ollama serve` owns :11434 decides which store is used. "
                "If a model 404s mid-run, this is why. Check `ss -ltnp | grep 11434` "
                "and pin OLLAMA_MODELS."
            ),
        )

    if present:
        return CheckResult(
            name="Model store",
            status=OK,
            detail=str(present[0]),
        )

    return CheckResult(
        name="Model store",
        status=WARN,
        detail="no readable model store found",
        remedy=(
            "The daemon may still be fine - the store can be owned by the "
            "`ollama` service user and unreadable from here."
        ),
    )


def check_system_memory() -> CheckResult:
    """Report RAM, swap and VRAM - the budget every context size is spent from."""

    total = total_ram_bytes()
    available = available_ram_bytes()
    swap = swap_total_bytes()
    vram = available_vram_bytes()
    gpus = gpu_names()

    parts = []

    if total and available:
        parts.append(f"RAM {available / GIB:.1f}/{total / GIB:.1f} GiB free")
    elif available:
        parts.append(f"RAM {available / GIB:.1f} GiB free")

    if vram:
        label = gpus[0] if gpus else "GPU"
        parts.append(f"VRAM {vram / GIB:.1f} GiB free ({label})")
    else:
        parts.append("no NVIDIA GPU detected (CPU inference)")

    detail = ", ".join(parts) or "unknown"

    if swap == 0:
        return CheckResult(
            name="System memory",
            status=WARN,
            detail=detail + ", no swap",
            remedy=(
                "With zero swap, an oversized KV cache fails hard instead of "
                "degrading. Keep contexts inside the memory plan."
            ),
        )

    return CheckResult(name="System memory", status=OK, detail=detail)


def check_data_files(paths: list[str]) -> CheckResult:
    """The NIAH corpus has to exist before we can build any haystack."""

    missing = [path for path in paths if not Path(path).is_file()]

    if missing:
        return CheckResult(
            name="Benchmark data",
            status=FAIL,
            detail="missing: " + ", ".join(missing),
            remedy=(
                "Run from the repository root - these paths are relative to the working directory."
            ),
        )

    return CheckResult(
        name="Benchmark data",
        status=OK,
        detail=f"{len(paths)} file(s) present",
    )


def check_tokenizer(provider: str, name: str) -> CheckResult:
    """Load the tokenizer now.

    tiktoken downloads its encoding on first use, so an offline machine fails
    here - much better than failing after the models are loaded.
    """

    from probebench.core.config import TokenizerConfig
    from probebench.tokenizers.factory import create_tokenizer

    try:
        tokenizer = create_tokenizer(TokenizerConfig(provider=provider, name=name))
        tokenizer.count("probe")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="Tokenizer",
            status=FAIL,
            detail=f"{provider}/{name} failed to load: {exc}",
            remedy=(
                "tiktoken fetches its encoding on first use; this needs network "
                "access once. Set TIKTOKEN_CACHE_DIR to reuse a warm cache offline."
            ),
        )

    return CheckResult(name="Tokenizer", status=OK, detail=f"{provider}/{name}")


def check_output_dir(output_dir: str) -> CheckResult:
    """Results are appended per case, so the directory must be writable now."""

    path = Path(output_dir) / "raw"

    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".probebench_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(
            name="Output directory",
            status=FAIL,
            detail=f"{path} is not writable: {exc}",
            remedy="Pick a writable --output-dir.",
        )

    free_bytes = shutil.disk_usage(path).free

    if free_bytes < GIB:
        return CheckResult(
            name="Output directory",
            status=WARN,
            detail=f"{path} writable, only {free_bytes / GIB:.1f} GiB free",
            remedy="Long runs write large JSONL files; free some space.",
        )

    return CheckResult(
        name="Output directory",
        status=OK,
        detail=f"{path} writable, {free_bytes / GIB:.1f} GiB free",
    )


def check_required_models(
    required: list[str],
    installed: list[str],
) -> tuple[CheckResult, list[str]]:
    """Which of the models this run needs are actually present."""

    available: set[str] = set(installed)

    for name in installed:
        if name.endswith(":latest"):
            available.add(name.rsplit(":", 1)[0])

    wanted = [name for name in dict.fromkeys(required) if name]

    missing = [
        name for name in wanted if name not in available and f"{name}:latest" not in available
    ]

    if missing:
        return (
            CheckResult(
                name="Required models",
                status=FAIL,
                detail="not installed: " + ", ".join(missing),
                remedy="Pull them with `ollama pull <model>` (ProbeBench can do this for you).",
            ),
            missing,
        )

    return (
        CheckResult(
            name="Required models",
            status=OK,
            detail=", ".join(wanted) or "none required",
        ),
        [],
    )


def run_health_checks(
    *,
    required_models: list[str] | None = None,
    data_files: list[str] | None = None,
    tokenizer_provider: str = "tiktoken",
    tokenizer_name: str = "cl100k_base",
    output_dir: str = "results",
    host: str | None = None,
) -> HealthReport:
    """Run every environment check and collect the results."""

    report = HealthReport()

    ollama_check, installed = check_ollama(host)
    report.checks.append(ollama_check)

    report.checks.append(check_model_store())
    report.checks.append(check_system_memory())

    if data_files:
        report.checks.append(check_data_files(data_files))

    report.checks.append(check_tokenizer(tokenizer_provider, tokenizer_name))
    report.checks.append(check_output_dir(output_dir))

    if required_models and ollama_check.status != FAIL:
        models_check, missing = check_required_models(required_models, installed)
        report.checks.append(models_check)
        report.missing_models = missing

    return report
