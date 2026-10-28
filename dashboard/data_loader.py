"""Schema-tolerant JSONL loader for Probebench run results.

Reads nested JSONL result trees, preserves missing values, supports the shapes
observed in schema 1.0 through 1.6, and records parse diagnostics instead of
silently dropping malformed lines.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def discover_jsonl_files(root: str | Path) -> list[Path]:
    """Find JSONL files under a directory recursively, or return a single file."""
    path = Path(root).expanduser()
    if path.is_file() and path.suffix.lower() == ".jsonl":
        return [path.resolve()]
    if not path.is_dir():
        return []
    return sorted(p.resolve() for p in path.rglob("*.jsonl") if p.is_file())


def file_fingerprint(paths: Iterable[Path]) -> tuple[tuple[str, int, int], ...]:
    """Return a Streamlit-cache-friendly file signature so changed files reload."""
    fingerprint = []
    for path in paths:
        try:
            stat = path.stat()
            fingerprint.append((str(path), stat.st_mtime_ns, stat.st_size))
        except OSError:
            fingerprint.append((str(path), -1, -1))
    return tuple(fingerprint)


def _normalise_record(raw: dict[str, Any], source_file: str, line_number: int) -> dict[str, Any]:
    run = _dict(raw.get("run"))
    model_raw = raw.get("model")
    model = _dict(model_raw)
    generation = _dict(raw.get("generation"))
    case = _dict(raw.get("case"))
    response = _dict(raw.get("response"))
    metrics = _dict(raw.get("metrics"))
    evaluation = _dict(raw.get("evaluation"))
    judge = _dict(evaluation.get("judge"))
    embedding = _dict(evaluation.get("embedding"))

    latency = _number(response.get("latency_sec"))
    prompt_eval_count = _number(response.get("prompt_eval_count"))
    num_ctx = _number(generation.get("num_ctx"))
    eval_count = _number(response.get("eval_count"))
    eval_duration_ns = _number(response.get("eval_duration_ns"))
    prompt_eval_exceeds_num_ctx = (
        prompt_eval_count > num_ctx if prompt_eval_count is not None and num_ctx is not None else None
    )
    prompt_eval_to_num_ctx_ratio = (
        float(prompt_eval_count) / float(num_ctx)
        if prompt_eval_count is not None and num_ctx is not None and num_ctx > 0
        else None
    )
    output_tps = None
    if eval_count is not None and eval_duration_ns and eval_duration_ns > 0:
        output_tps = float(eval_count) / (float(eval_duration_ns) / 1_000_000_000)

    depth = case.get("realised_depth")
    if depth is None:
        depth = case.get("depth")

    status = response.get("status")
    if not status:
        status = "error" if response.get("error") else "unknown"
    status_normalised = str(status).strip().lower()
    has_error = bool(response.get("error")) or status_normalised in {
        "error", "failed", "failure", "exception", "timeout", "evaluation_error", "eval_error"
    }

    # In early schema records, `model` was saved as a string rather than a dict.
    model_name = model.get("name")
    if not model_name and isinstance(model_raw, str):
        model_name = model_raw
    if not model_name:
        model_name = "unknown"

    record: dict[str, Any] = {
        "source_file": source_file,
        "line_number": line_number,
        "schema_version": str(raw.get("schema_version", "unknown")),
        "run_id": str(run.get("run_id", "unknown")),
        "benchmark": str(run.get("benchmark", case.get("family", "unknown"))),
        "experiment": str(run.get("experiment", case.get("experiment", "unknown"))),
        "model_name": str(model_name),
        "model_family": model.get("family"),
        "model_provider": model.get("provider"),
        "parameter_size": model.get("parameter_size"),
        "quantization": model.get("quantization"),
        "supported_context_window": _number(model.get("supported_context_window")),
        "num_ctx": num_ctx,
        "prompt_eval_exceeds_num_ctx": prompt_eval_exceeds_num_ctx,
        "prompt_eval_to_num_ctx_ratio": prompt_eval_to_num_ctx_ratio,
        "kv_cache_type": generation.get("kv_cache_type_effective", generation.get("kv_cache_type_requested")),
        "judge_enabled": judge.get("enabled"),
        "judge_model": judge.get("model"),
        "embedding_enabled": embedding.get("enabled"),
        "case_id": case.get("case_id", case.get("case_key", "unknown")),
        "case_key": case.get("case_key"),
        "case_fingerprint": case.get("case_fingerprint"),
        "prompt_sha256": case.get("prompt_sha256"),
        "system_prompt_sha256": case.get("system_prompt_sha256"),
        "target_tokens": _number(case.get("target_tokens")),
        "context_tokens": _number(case.get("context_tokens")),
        "depth": _number(depth),
        "answerable": case.get("answerable") if isinstance(case.get("answerable"), bool) else None,
        "fact_count": _number(case.get("fact_count")),
        "distractor_count": _number(case.get("distractor_count")),
        "registry_size": _number(case.get("registry_size")),
        "target_subject": case.get("target_subject"),
        "query_entity_name": case.get("query_entity_name"),
        "response_status": str(status),
        "has_error": has_error,
        "error": response.get("error"),
        "latency_sec": latency,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "prompt_eval_duration_ns": _number(response.get("prompt_eval_duration_ns")),
        "eval_duration_ns": eval_duration_ns,
        "total_duration_ns": _number(response.get("total_duration_ns")),
        "output_tokens_per_sec": output_tps,
        "expected": response.get("expected"),
        "predicted": response.get("predicted"),
        "question": case.get("question"),
        "needle": case.get("needle"),
        "_raw_record": raw,
    }
    for name, value in metrics.items():
        numeric_value = _number(value)
        if numeric_value is not None:
            record[f"metric__{name}"] = float(numeric_value)
    return record


def read_jsonl_files(fingerprint: tuple[tuple[str, int, int], ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and normalise rows. Return records plus parse/data diagnostics."""
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for path_string, _mtime_ns, _size in fingerprint:
        path = Path(path_string)
        if not path.is_file():
            diagnostics.append({"file": path_string, "line": None, "issue": "File disappeared or is not readable."})
            continue
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as exc:
            diagnostics.append({"file": path_string, "line": None, "issue": f"Could not open file: {exc}"})
            continue
        with handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    diagnostics.append({"file": path_string, "line": line_number, "issue": f"Invalid JSON: {exc.msg}"})
                    continue
                if not isinstance(raw, dict):
                    diagnostics.append({"file": path_string, "line": line_number, "issue": "JSONL record is not a JSON object."})
                    continue
                if not any(isinstance(raw.get(key), dict) for key in ("response", "case", "run", "metrics")):
                    diagnostics.append({"file": path_string, "line": line_number, "issue": "Record does not look like a Probebench result; retained for diagnostics only."})
                    continue
                try:
                    records.append(_normalise_record(raw, path_string, line_number))
                except Exception as exc:  # Keep the dashboard useful if one record has a surprising shape.
                    diagnostics.append({"file": path_string, "line": line_number, "issue": f"Could not normalise record: {type(exc).__name__}: {exc}"})
    return records, diagnostics
