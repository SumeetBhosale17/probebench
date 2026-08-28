# ProbeBench

A controlled evaluation framework for **diagnosing** LLM failures, not just
scoring them.

## What this project is for

Most benchmarks answer "how well did the model do?" ProbeBench is built to
answer harder questions:

- **Why** does a model fail on a given input?
- **Where** in the input does it fail — position, length, structure?
- **Do different models fail on the same inputs**, or on different ones?
- Is a failure a property of the *model*, the *task*, or the *serving stack*?

That reframing drives every design decision here. A score with no attached
diagnostic context is close to useless for us. Prefer recording *more*
structured metadata per case over producing a tidier headline number.

**This is a research project intended to produce a paper.** Treat measurement
validity as a first-class concern, not a nice-to-have. When a change could
affect what is being measured — not just how fast it runs — say so explicitly
and document it.

## Scope

Long-range dependency / NIAH is the **first** benchmark family, not the
scope. More families are planned (a `benchmarks/hallucination/` stub already
exists). Build for plurality:

- New experiments are registered in `src/probebench/experiments/registry.py`
  as one `ExperimentSpec`. The CLI, the `all` command, and the health check
  all read from that registry — adding an experiment should require no edits
  elsewhere.
- Keep benchmark-specific logic under
  `benchmarks/<family>/<EXPERIMENT>/` and
  `evaluation/<family>/<EXPERIMENT>/`. Shared machinery lives in `core/`.
- Resist hardcoding NIAH assumptions into `core/`. If something in `core/`
  mentions needles or haystacks, it is in the wrong place.

## Read these first

- **[docs/DESIGN.md](docs/DESIGN.md)** — the two production failures that
  shaped the architecture, root-cause analysis with the arithmetic, and
  what/how/why for each subsystem. Read before changing execution flow,
  memory handling, or the judge.
- **[docs/LIMITATIONS.md](docs/LIMITATIONS.md)** — every known limitation,
  graded BLOCKING / MAJOR / MINOR. Read before making any claim about
  results.

When you discover a new limitation, add it to LIMITATIONS.md with its
severity and what would be needed to remove it. When you change architecture,
update DESIGN.md's what/how/why for that subsystem.

## Non-negotiable invariants

These encode expensive lessons. Changing any of them needs an explicit
decision, not a drive-by refactor.

1. **A failed evaluator leaves its metric ABSENT from `metrics`, never
   `0.0`.** A judge that errored is missing data; recording zero silently
   biases every aggregate downward. See `BenchmarkRunner.evaluate`.

2. **Never call a model without a memory preflight.** Requesting a context
   the host cannot hold kills the Ollama runner and, historically, took the
   whole run with it. `core/preflight.py` gates this.

3. **The judge's `num_ctx` is pinned and must stay pinned.** Ollama keys a
   `llama-server` runner on `(model, num_ctx)`. An unpinned judge spawns a
   new runner per distinct generation `num_ctx` and evicts the generation
   model on every case. This was a real production failure.

4. **`--context` is a CEILING that DROPS oversized cases — it does not
   shrink them.** Changing case sizes is `--target-tokens`. Skipped cases
   must always be reported, never silently dropped.

5. **A single case failure must not abort a run** unless `--fail-fast` is
   given. Record `status` and `error` on the result and continue.

6. **Pulling a model is confirmed, never implicit.** Non-interactive shells
   refuse. It is a multi-gigabyte network download.

7. **Bump `CURRENT_SCHEMA_VERSION` when `to_record()` changes**, and register
   a migration in `core/migrations.py`. (This was violated once already —
   see LIMITATIONS §5.2.)

## The KV cache formula

Load-bearing arithmetic, validated against a real llama.cpp failure:

```
kv_bytes_per_token = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element
```

For `qwen3:4b` (36 layers, 8 KV heads, head_dim 128, f16): 147,456 B/token
= 144 KiB/token. At 256,000 tokens that is 36,000 MiB — matching the observed
allocation failure exactly.

Fields come from GGUF metadata via `OllamaModelRegistry.inspect()`. Keys are
architecture-prefixed (`qwen3.block_count`), so use the `_find_int` suffix
matcher rather than literal keys.

## Layout

```
src/probebench/
  core/          # provider-agnostic machinery
    config.py    # RunConfig + Sweep/Execution/Judge/Embedding configs
    runner.py    # generate() / evaluate() split — enables two-phase
    preflight.py # KV arithmetic, memory budget, capability planning
    health.py    # pre-run environment checks
    retry.py     # transient-failure backoff
    result.py    # BenchmarkResult + to_record() (schema-versioned)
    schema.py    # CURRENT_SCHEMA_VERSION
    migrations.py
  benchmarks/<family>/<EXPT>/   # case generation
  evaluation/<family>/<EXPT>/   # evaluators (lexical, semantic, judge)
  experiments/registry.py       # ExperimentSpec registry — add new here
  experiments/<family>/<EXPT>/run.py  # orchestration
  models/        # Ollama client, registry, installer, host resolution
  reporting/     # jsonl (wired); markdown/csv/json (currently dead code)
```

## Commands

```bash
uv run probebench <model>                    # run all experiments
uv run probebench doctor [model]             # environment check
uv run probebench plan <model>               # what contexts fit this machine
uv run probebench <model> --dry-run          # cases + memory plan, no calls
uv run probebench models inspect <model>     # incl. KV cache per token
```

Always available: `--target-tokens`, `--profile {auto,quick,standard,full}`,
`--depths`, `--needles`, `--judge-model`, `--fail-fast`, `--single-phase`,
`--skip-memory-check`, `--dry-run`, `--yes`.

## Development

```bash
uv run pytest                  # unit tests; -m "not integration" to skip Ollama
uv run ruff check src/         # line-length 100, py312, E/F/I/UP/B/SIM
uv run pyright                 # currently clean — keep it that way
./scripts/smoke_test.sh        # 16 CLI checks, needs a live Ollama
```

Python ≥3.12. `uv` for dependency management. Ollama is currently the only
model backend (`model_provider` is hardcoded).

## Conventions

- Comments explain **why**, not what. The codebase has several non-obvious
  decisions (404 being retryable, `num_ctx` bucketing, absent-vs-zero
  metrics) — those all carry a comment explaining the reasoning. Match that.
- Prefer explicit dataclass config over kwargs soup. `RunConfig` composes
  `SweepConfig` / `ExecutionConfig` / `JudgeConfig` / `EmbeddingConfig`.
- Log what was skipped and why. Silent filtering is the enemy of a valid
  benchmark.
- Record provenance in results: tokenizer, `num_ctx`, KV precision, judge
  model, model geometry. A result you cannot reproduce is not a result.

## Current highest-priority issues

From LIMITATIONS.md, in order:

1. **Tokenizer mismatch (§1.1, BLOCKING).** Haystacks are built with
   `tiktoken cl100k_base` but served to models with different tokenizers, so
   "4,000 tokens" is nominal and differs per model family. This invalidates
   the x-axis of every context-length curve and blocks cross-model claims.
2. **No repeats (§1.4)** — `--needles 1` means one Bernoulli sample per grid
   cell, so no error bars are possible.
3. **No seed control (§1.3)** — runs are not reproducible.
4. **Self-judging (§1.2)** — the judge defaults to the generation model.
5. **Two-phase data loss (§4.1)** — nothing is written to disk until
   generation finishes; a crash loses the whole run. `--single-phase` is
   safer for long runs until checkpointing lands.
6. **Reporting layer is dead code (§5.1)** — `markdown.py`, `csv.py`,
   `json.py` are never called.
