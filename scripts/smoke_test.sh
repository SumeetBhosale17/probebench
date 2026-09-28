#!/usr/bin/env bash
# ProbeBench smoke test.
#
# Exercises every code path that does NOT need a long benchmark run:
# CLI wiring, health checks, capability planning, memory preflight, and
# failure isolation. Safe to run on any machine with Ollama installed.
#
#   ./scripts/smoke_test.sh [model]
#
# Exits non-zero on the first unexpected result.

set -uo pipefail

MODEL="${1:-qwen3:4b}"
PB="${PB:-probebench}"

pass=0
fail=0

# Runs a command and asserts on its exit status and (optionally) that its
# output matches a pattern.
check() {
    local name="$1" expected_status="$2" pattern="${3:-}"
    shift 3 2>/dev/null || shift 2

    local output status
    output="$("$@" 2>&1)"
    status=$?

    if [[ "$expected_status" != "any" && "$status" != "$expected_status" ]]; then
        echo "FAIL  $name (exit $status, expected $expected_status)"
        echo "$output" | tail -5 | sed 's/^/        /'
        ((fail++))
        return
    fi

    if [[ -n "$pattern" ]] && ! grep -qE "$pattern" <<<"$output"; then
        echo "FAIL  $name (missing /$pattern/)"
        echo "$output" | tail -5 | sed 's/^/        /'
        ((fail++))
        return
    fi

    echo "ok    $name"
    ((pass++))
}

echo "ProbeBench smoke test - model: $MODEL"
echo "============================================================"

# --- CLI wiring -----------------------------------------------------
check "--help"                    0 "probebench"        "$PB" --help
check "experiments list"          0 "NIAH"              "$PB" experiments list
check "models list"               0 "Installed Ollama"  "$PB" models list
check "models inspect"            0 "KV cache per token" "$PB" models inspect "$MODEL"

# --- environment ----------------------------------------------------
check "doctor (no model)"         0 "Ollama daemon"     "$PB" doctor
check "doctor (with model)"       0 "Required models"   "$PB" doctor "$MODEL"
check "doctor rejects bad model"  1 "not installed"     "$PB" doctor definitely-not-a-model:1b

# --- capability planning --------------------------------------------
check "plan"                      0 "Recommended sweep" "$PB" plan "$MODEL"
check "plan flags oversize"       0 "TOO LARGE"         "$PB" plan "$MODEL" --target-tokens 256000

# --- case generation and memory preflight ---------------------------
check "dry-run (auto profile)"    0 "Dry run"           "$PB" "$MODEL" --dry-run
check "dry-run (quick profile)"   0 "Dry run"           "$PB" "$MODEL" --profile quick --dry-run
check "explicit target-tokens"    0 "Dry run"           "$PB" "$MODEL" --target-tokens 4000,8000 --dry-run
check "preflight refuses 256k"    1 "Insufficient memory" \
      "$PB" "$MODEL" --target-tokens 256000 --dry-run
check "--context drops oversize"  1 "No cases generated" \
      "$PB" "$MODEL" --target-tokens 64000 --context 8000 --dry-run
check "bare model = all"          0 "long_range_dependency/NIAH" "$PB" "$MODEL" --dry-run

# --- shorthand equivalence ------------------------------------------
check "explicit run subcommand"   0 "Dry run" \
      "$PB" run --benchmark long_range_dependency --experiment NIAH \
      --model "$MODEL" --profile quick --dry-run

echo "============================================================"
echo "passed: $pass   failed: $fail"

[[ "$fail" -eq 0 ]]
