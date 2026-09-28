# ProbeBench

A controlled evaluation framework for **diagnosing** LLM failures, not just
scoring them.

Most benchmarks answer "how well did the model do?" ProbeBench is built to
answer harder questions:

- **Why** does a model fail on a given input?
- **Where** in the input does it fail — position, length, structure?
- **Do different models fail on the same inputs**, or on different ones?
- Is a failure a property of the *model*, the *task*, or the *serving stack*?

Every case records structured provenance — tokenizer, requested context, KV
precision, model geometry, judge model, per-evaluator diagnostics — so a
result can be interrogated rather than just reported.

> **Research project.** Measurement validity is treated as a first-class
> concern. Read [docs/LIMITATIONS.md](docs/LIMITATIONS.md) before making any
> claim from ProbeBench output — several known threats to validity are
> currently unresolved.

---

## Status

| | |
|---|---|
| Benchmark families | `long_range_dependency` (NIAH). More planned. |
| Model backend | Ollama only |
| Platform | Linux (memory detection reads `/proc/meminfo`) |
| Python | ≥ 3.12 |

---

## Install

```bash
git clone <repo> && cd probebench
uv sync
```

Requires a running [Ollama](https://ollama.com) daemon. Verify the whole
environment in one command:

```bash
uv run probebench doctor
```

---

## Quickstart

```bash
# 1. Is this machine set up correctly?
uv run probebench doctor qwen3:4b

# 2. What context sizes can this machine actually run?
uv run probebench plan qwen3:4b

# 3. Preview the cases and memory plan without calling the model
uv run probebench qwen3:4b --dry-run

# 4. Run everything
uv run probebench qwen3:4b
```

`probebench <model>` is shorthand for `probebench all <model>` — it runs
every registered experiment and prints a summary per context length.

---

## CLI reference

All commands are prefixed with `uv run` (or use the installed `probebench`
entry point directly).

### Commands

| Command | Purpose | Exit |
|---|---|---|
| `probebench <model>` | Shorthand for `all <model>` | 0 / 1 |
| `probebench all <model>` | Run every registered experiment against one model | 0 / 1 |
| `probebench run --benchmark F --experiment E --model M` | Run one specific experiment | 0 / 1 |
| `probebench doctor [model]` | Environment and dependency check | 0 ok / 1 failed |
| `probebench plan <model>` | Per-context memory feasibility table | 0 |
| `probebench models list` | Installed Ollama models | 0 |
| `probebench models inspect <model>` | Model geometry, context, KV cost per token | 0 / 1 |
| `probebench models pull <model>` | Install a model (prompts first) | 0 / 1 |
| `probebench experiments list` | Registered experiments | 0 |

### Options for `all` and `run`

| Flag | Default | Description |
|---|---|---|
| `--target-tokens` | *(from profile)* | Comma-separated haystack sizes, e.g. `4000,8000,16000`. Overrides `--profile`. |
| `--profile` | `auto` | `auto` \| `quick` (4k–8k) \| `standard` (4k–32k) \| `full` (4k–128k). `auto` sizes the sweep to this machine's free memory; the fixed profiles do not, so `full` will be refused on a small host. |
| `--context` | *(model max)* | **CEILING** on model context. Oversized cases are **dropped, not shrunk**. |
| `--depths` | `0,0.25,0.5,0.75,1.0` | Needle depths in `[0,1]`. |
| `--needles` | `1` | Needles per (length, depth) cell. Raise for error bars. |
| `--judge-model` | *generation model* | LLM judge. **Set this explicitly** to avoid self-judging. |
| `--judge-context` | `4096` | Pinned judge context. Keep fixed — avoids per-case model reloads. |
| `--embedding-model` | `nomic-embed-text` | Embedding model for semantic similarity. |
| `--tokenizer` | `cl100k_base` | tiktoken encoding used to build haystacks. |
| `--kv-cache-type` | `f16` | `f16` \| `q8_0`. Precision assumed when estimating memory. |
| `--no-judge` | off | Skip the LLM judge evaluator. |
| `--no-embedding` | off | Skip the semantic similarity evaluator. |
| `--fail-fast` | off | Abort on first case failure instead of recording and continuing. |
| `--single-phase` | off | Judge each case immediately. Slower (model reloads) but writes results incrementally. |
| `--skip-memory-check` | off | Run even when the memory plan says a context will not fit. |
| `--skip-health-check` | off | Skip pre-run environment checks. |
| `--dry-run` | off | Build cases and print the memory plan without calling any model. |
| `--yes`, `-y` | off | Install missing models without prompting. |
| `--output-dir` | `results` | Directory for raw results. |
| `--experiments` | *(all)* | *(`all` only)* Comma-separated subset, e.g. `NIAH`. |
| `--benchmark`, `--experiment`, `--model` | — | *(`run` only)* Required. |

### Options for other commands

| Command | Flags |
|---|---|
| `doctor` | `[model]`, `--judge-model`, `--embedding-model`, `--tokenizer`, `--output-dir`, `--yes` |
| `plan` | `<model>`, `--target-tokens`, `--kv-cache-type` |
| `models pull` | `<model>`, `--yes` |

### Environment variables

| Variable | Effect |
|---|---|
| `OLLAMA_HOST` | Ollama endpoint. Accepts `host:port` or a full URL. |
| `OLLAMA_MODELS` | Model store path. Set it to pin which store is used. |
| `OLLAMA_KV_CACHE_TYPE` | KV precision **for Ollama**. Pair with `--kv-cache-type`. |
| `OLLAMA_FLASH_ATTENTION` | Required by older Ollama for quantised KV cache. |
| `TIKTOKEN_CACHE_DIR` | Reuse a warm tiktoken cache offline. |

---

## Worked examples

```bash
# Reproducible sweep — pin target-tokens and the judge for reported results
uv run probebench qwen3:4b \
    --target-tokens 4000,8000,16000,32000 \
    --depths 0,0.25,0.5,0.75,1.0 \
    --needles 5 \
    --judge-model llama3.1:8b

# Fast smoke run
uv run probebench qwen3:4b --target-tokens 4000 --depths 0

# Lexical metric only — no judge, no embeddings
uv run probebench qwen3:4b --no-judge --no-embedding

# One experiment explicitly
uv run probebench run \
    --benchmark long_range_dependency --experiment NIAH \
    --model qwen3:4b --profile quick

# Benchmark a remote Ollama host
OLLAMA_HOST=192.168.1.50:11434 uv run probebench doctor

# Halve KV cache cost to reach longer contexts
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 \
    uv run probebench qwen3:4b --kv-cache-type q8_0 --target-tokens 64000
```

---

## Understanding the memory plan

Long-context benchmarking is bounded by the KV cache, which grows linearly
with context:

```
kv_bytes_per_token = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element
```

For `qwen3:4b` that is **144 KiB per token** — so a 256k-token context needs
**35 GiB of KV cache alone**, before model weights. `probebench plan` makes
this explicit before you waste an hour discovering it:

```
     context    weights   KV cache      total     budget  verdict
  ----------  ---------  ---------  ---------  ---------  -------
       4,608       2.3G       0.6G       3.0G      15.7G  OK
      32,768       2.3G       4.5G       7.3G      15.7G  OK
      64,512       2.3G       8.9G      12.1G      15.7G  OK
     128,512       2.3G      17.6G      21.7G      15.7G  TOO LARGE
```

**A model's advertised context window is not the context window you can
benchmark.** `qwen3:4b` advertises 262,144 tokens; the reference machine
(23 GiB RAM, 4 GiB VRAM) tops out near 88,800.

---

## Results

Raw results are JSON Lines, one record per case, at:

```
results/raw/<family>_<experiment>_<model>_<run_id>.jsonl
results/raw/<family>_<experiment>_<model>_<run_id>.log
```

Each record carries `run`, `model` (incl. geometry), `generation` (incl.
`num_ctx`), `tokenization`, `evaluation` config, `case` metadata, `response`
(incl. `status` and `error`), `metrics`, and `evaluation_details`.

### Reading `status`

| `status` | Meaning |
|---|---|
| `ok` | Generation and all evaluators succeeded |
| `generation_error` | The model call failed; `error` holds the reason |
| `evaluation_error` | At least one evaluator failed; see `evaluation_details` |

**A failed evaluator leaves its metric absent from `metrics` — never `0.0`.**
A judge that errored is missing data, not a score of zero. When aggregating,
report per-metric N alongside every mean.

```bash
# Inspect a run
jq '.response.status, .metrics' results/raw/<file>.jsonl

# Count outcomes
jq -r '.response.status' results/raw/<file>.jsonl | sort | uniq -c
```

---

## Development

```bash
uv run pytest                      # unit tests
uv run pytest -m "not integration" # skip tests needing a live Ollama
uv run ruff check src/
uv run pyright
./scripts/smoke_test.sh            # 16 CLI checks, needs a live Ollama
```

### Adding a benchmark

1. Add case generation under `src/probebench/benchmarks/<family>/<EXPT>/`.
2. Add evaluators under `src/probebench/evaluation/<family>/<EXPT>/`.
3. Add an orchestration `run.py` under `src/probebench/experiments/<family>/<EXPT>/`.
4. Register one `ExperimentSpec` in
   `src/probebench/experiments/registry.py`.

The CLI, the `all` command, and the health check all read from that registry
— no other edits needed.

---

## Documentation

- **[CLAUDE.md](CLAUDE.md)** — project conventions and non-negotiable
  invariants
- **[docs/DESIGN.md](docs/DESIGN.md)** — the failures that shaped the
  architecture, and what/how/why per subsystem
- **[docs/LIMITATIONS.md](docs/LIMITATIONS.md)** — known limitations graded
  BLOCKING / MAJOR / MINOR

---

## Known limitations

Summarised from [docs/LIMITATIONS.md](docs/LIMITATIONS.md). The first is
**blocking for publishable results**:

1. **Tokenizer mismatch.** Haystacks are built with `tiktoken cl100k_base`
   but served to models with different tokenizers, so "4,000 tokens" is
   nominal and differs per model family.
2. **No repeats by default.** `--needles 1` is one sample per grid cell — no
   error bars. Use `--needles 5` or more.
3. **No seed control.** Runs are not bit-reproducible.
4. **Self-judging by default.** The judge falls back to the generation
   model. Always pass `--judge-model`.
5. **Two-phase writes nothing until generation completes.** A crash loses the
   run; `--single-phase` is safer for very long runs.
6. **Linux + NVIDIA only** for memory detection. Elsewhere the budget is
   under-estimated and runs may be refused — use `--skip-memory-check`.

---

## Authors

See `pyproject.toml`.
