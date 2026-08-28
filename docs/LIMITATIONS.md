# ProbeBench — Known Limitations

Status: as of 2026-08-29, branch `long-context-benchmark`.

This document records every limitation identified so far, with the reason it
exists and what would be needed to remove it. Sections 1 and 2 are the ones
that matter for publishable claims; the rest are engineering debt.

Severity key:
- **BLOCKING** — must be resolved before results are publishable
- **MAJOR** — must be disclosed in the paper's threats-to-validity section
- **MINOR** — engineering debt, no effect on measurement validity

---

## 1. Threats to measurement validity

### 1.1 Tokenizer mismatch between haystack construction and inference — BLOCKING

Haystacks are built and measured with `tiktoken`/`cl100k_base`, a GPT-4
tokenizer. They are then served to models with entirely different
vocabularies. `probebench models inspect qwen3:4b` reports:

```
Tokenizer model:    gpt2
Tokenizer pre:      qwen2
```

So a case labelled "4,000 tokens" is 4,000 **cl100k** tokens. The number of
tokens the model actually sees is different, and differs *per model family*.

Consequences:
- The x-axis of every context-length curve is only nominal.
- Cross-model comparisons at "the same context length" are not actually at
  the same context length.
- `context_buffer_tokens = 512` may be insufficient if the target model
  tokenizes the text less efficiently than cl100k does, silently pushing the
  prompt past the requested `num_ctx`.

Fix: tokenize with the target model's own tokenizer (Ollama exposes
`tokenizer.ggml.model` / `.pre`; the GGUF vocab can be read directly, or
`/api/embed`-style token counts obtained from the server). Until then, report
context lengths as "cl100k-equivalent" and do not compare across families.

### 1.2 LLM-as-judge defaults to the generation model — MAJOR

`RunConfig.resolved_judge_model()` falls back to `generation_model` when
`--judge-model` is not given. The default configuration therefore has a model
grading its own output — a self-evaluation bias.

Fix: always pass an explicit, fixed `--judge-model` for reported results, and
state it. Ideally use a model from a different family than any system under
test.

### 1.3 No seed control; the judge is not reproducible — MAJOR

The judge uses `temperature: 0`, but no `seed` is set anywhere in the
codebase, and llama.cpp's greedy decoding can still vary with batching and
numerical non-determinism. Generation likewise runs at the model's default
sampling parameters (for `qwen3:4b`: `temperature 0.6, top_k 20, top_p 0.95`).

Consequence: re-running the same command can produce different scores. No
run is bit-reproducible.

Fix: thread a `seed` option through `model_options` and the judge's
`options`; pin generation temperature explicitly rather than inheriting the
Modelfile default.

### 1.4 No repeats, so no error bars — MAJOR

`needles_per_configuration` defaults to 1. A cell in the (length × depth)
grid is therefore a single Bernoulli sample. No variance estimate is possible
and the published heatmap would be pure noise at the cell level.

Fix: `--needles N` with N ≥ 5, plus repeated runs, and report mean ± CI.

### 1.5 `semantic_similarity` has almost no discriminative power — MAJOR

Cosine similarity between embeddings of two short extraction answers is
near-saturated. Observed values across successful runs were `1.0` and
`0.9999999999999998`; the metric does not separate correct from incorrect on
this task. Its own docstring already notes it is a similarity metric, not a
correctness metric.

Fix: either drop it from NIAH reporting or replace it with a metric that
discriminates (e.g. normalised edit distance on the extracted code).

### 1.6 Auto-sizing makes runs machine-dependent — MAJOR

`--profile auto` (the default) chooses `target_tokens` from the *host's* free
RAM and VRAM. Two machines will produce different sweeps for the same
command, and the same machine will differ depending on what else is running.

Mitigation in place: the chosen sweep is printed and recorded.

Fix for the paper: **always pin `--target-tokens` explicitly** for reported
results. Treat `auto` as an exploration convenience only.

### 1.7 Absent metrics change aggregation denominators — MAJOR

When an evaluator fails, its metric key is deliberately **absent** from
`metrics` rather than recorded as `0.0` (see `BenchmarkRunner.evaluate`).
This is the honest choice — a judge that errored is missing data, not a zero
score — but it means different metrics in the same run can be averaged over
different numbers of cases.

Fix: report per-metric N alongside every mean, and report the count of
`evaluation_error` cases.

### 1.8 `num_ctx` bucketing over-allocates context — MINOR

`num_ctx` is rounded up to a 512-token boundary so that all cases at one
target size share a single Ollama runner. A nominal 16,000-token case
actually runs with `num_ctx = 16,896`.

The extra context is empty, so the needle's *relative* depth is unchanged,
but the model is not run at a tight context limit. Disclose the bucketing
rule if context-limit saturation is ever a claim.

### 1.9 Fixed filler corpus and needle set — MINOR

All haystacks come from one 3.3 MB `filler_text.txt` and one `needles.txt`.
Domain, register, and repetition effects are unmeasured and confounded with
the length effect.

### 1.10 Depth 1.0 places the needle adjacent to the question — MINOR

The prompt is `f"{context}\n\nQuestion: {question}"`. At `depth=1.0` the
needle sits immediately before the question, which is a qualitatively
different retrieval task from `depth=0.0`. This is inherent to NIAH but
should be stated rather than treated as a uniform axis.

### 1.11 Judge input is truncated at 4,000 characters — MINOR

`OllamaJudge._truncate` caps the graded response so it cannot overflow the
pinned judge context. A pathologically long model answer is graded on its
first 4,000 characters only. Truncation is marked inline in the judge prompt
but is not currently recorded in `evaluation_details`.

---

## 2. Memory model limitations

### 2.1 The estimate is an approximation, not an allocation trace — MAJOR

`estimate_case_bytes` computes:

```
weights_bytes + kv_bytes + 0.10 * kv_bytes
```

where `kv_bytes = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element · num_ctx`.

The KV term is exact and was validated against a real failure: for
`qwen3:4b` at `num_ctx = 256,000` it predicts 35.2 GiB, and the observed
llama.cpp error was `attempted to allocate 36000.00 MB` (= 35.16 GiB). The
KV formula is correct.

The **10 % compute-buffer allowance is a heuristic**. llama.cpp's actual
compute buffer depends on batch size and graph structure. Memory
fragmentation, the runner process's own overhead, and concurrent allocations
are not modelled.

Consequence: the total is approximate in both directions. Treat verdicts near
the budget boundary as unreliable.

### 2.2 The budget is a snapshot of free memory — MAJOR

`available_ram_bytes()` reads `MemAvailable` and `available_vram_bytes()`
shells out to `nvidia-smi`, both at preflight time. Another process can
allocate between the check and the model load. The `0.85` headroom fraction
is an arbitrary safety margin, not a derived bound.

### 2.3 Non-NVIDIA GPUs are invisible — MAJOR

VRAM detection is `nvidia-smi` only. On AMD (ROCm), Intel Arc, or Apple
Silicon, VRAM is counted as **zero** and the budget becomes RAM-only.

Direction of error is *conservative* — the tool refuses runs that would
actually fit — so it fails safe, but it will block legitimate work. Use
`--skip-memory-check` on such hosts.

### 2.4 Memory detection is Linux-only — MAJOR

`total_ram_bytes`, `available_ram_bytes` and `swap_total_bytes` all parse
`/proc/meminfo`. On macOS or Windows they return `None`, which collapses the
budget to `0`, and **every context size is judged TOO LARGE**.

There is currently no guard for this. Porting beyond Linux requires either
platform-specific implementations or a "budget unknown → skip enforcement"
branch.

### 2.5 KV geometry may be missing for some models — MINOR

`kv_bytes_per_token()` returns `None` unless `block_count`, `kv_head_count`
and `head_dim` are all present in the GGUF metadata. `head_dim` is derived
from `embedding_length // head_count` when `key_length` is absent, which is
wrong for architectures where those differ (e.g. some MLA/DeepSeek variants).
When geometry is unavailable the preflight silently no-ops.

### 2.6 `q4_0` KV cache cannot be expressed — MINOR

`--kv-cache-type` accepts only `f16` and `q8_0`, because
`kv_cache_bytes_per_element` is an `int`. `q4_0` (~0.5 bytes/element) cannot
be represented.

---

## 3. Platform and portability

### 3.1 Ollama is the only backend — MAJOR

`model_provider` is hardcoded to `"ollama"` in `BenchmarkRunner.evaluate`.
There is no adapter for OpenAI, Anthropic, vLLM, llama.cpp direct, or
HuggingFace. Any cross-provider claim is currently out of reach.

### 3.2 Model-store detection is distribution-specific — MINOR

`_store_candidates()` queries `systemctl show ollama --property=Environment`
and falls back to a hardcoded candidate list:

| Distribution | Store | Detected |
|---|---|---|
| EndeavourOS / Arch | `/var/lib/ollama` (unit sets `OLLAMA_MODELS`) | verified |
| Debian / Ubuntu | `/usr/share/ollama/.ollama/models` | in candidate list, unverified |
| macOS | `~/.ollama/models` | in candidate list, unverified |

On systems without `systemctl`, or with a store in an unlisted location, the
check degrades to a warning. It also cannot read a root-owned store, which
produces a false "no readable model store found" warning even when the daemon
is healthy. This is a warning, not a failure — runs proceed.

### 3.3 No `--host` flag — MINOR

The Ollama endpoint comes from `OLLAMA_HOST` (via
`probebench.models.host.default_ollama_host`) or the default. There is no
per-invocation override flag.

---

## 4. Robustness and operations

### 4.1 Two-phase execution writes nothing until phase 1 completes — MAJOR

This is a **regression relative to single-phase** and the most important
operational caveat.

`_run_two_phase` generates every response first, holding them in memory, and
only writes JSONL during the evaluation phase. A crash, OOM kill, or Ctrl-C
during generation loses the entire run — including cases that had already
succeeded.

Single-phase (`--single-phase`) writes each result as it completes and does
not have this problem, at the cost of per-case model reloads.

Fix: checkpoint the phase-1 responses to disk as they arrive, and resume from
that checkpoint.

### 4.2 Retrying HTTP 404 can mask a genuinely removed model — MINOR

`RETRYABLE_STATUS` includes `404`, deliberately: on a memory-thrashing host
Ollama can transiently fail to resolve a model it is mid-unload. A model that
is genuinely absent is caught by `ensure_availability()` before the run
starts, so a 404 *during* a run is more likely transient than real.

Residual risk: a model deleted by another user mid-run costs three retries
(~6 s) per call before being recorded as an error.

### 4.3 `keep_alive="30m"` holds memory after the run ends — MINOR

Models stay resident for 30 minutes after the last call. On a shared machine
this denies memory to other users. There is no CLI flag to change it.

### 4.4 Sequential execution only — MINOR

Cases run one at a time. A full sweep on a small GPU takes hours. There is no
concurrency, batching across cases, or resume-from-partial-results.

### 4.5 A mistyped subcommand becomes a model name — MINOR

`_normalize_argv` treats any first argument that is not a known subcommand
and does not start with `-` as a model name. `probebench modles list`
therefore becomes `probebench all "modles list"` and reports a missing model
rather than an unknown command.

### 4.6 The 404 root cause on the lab machine is unconfirmed — MINOR

The `model 'qwen3:8b' not found (404)` failure at case 3/20 was diagnosed as
the Ollama server's view of its model store changing mid-run (server restart
under memory pressure, or two competing stores). Retries and the startup
preflight mitigate it, but the underlying cause was never confirmed on that
host — the diagnostics in the test guide were not run there.

---

## 5. Architectural gaps

### 5.1 The reporting layer is dead code — MAJOR

`reporting/markdown.py`, `reporting/csv.py` and `reporting/json.py` are
**never called from anywhere**. Only `reporting/jsonl.py` is wired in.
`write_long_range_summary()` — including its status-aware handling — is
unreachable.

The CLI prints its own inline summary table instead. There is currently no
command that produces the Markdown report, no `probebench report`
subcommand, and no aggregation across runs.

### 5.2 Result schema version was not bumped — MAJOR

`status` and `error` were added to `BenchmarkResult.to_record()` while
`CURRENT_SCHEMA_VERSION` remained `"1.0"`. Records written before and after
this change both claim schema `1.0` but have different shapes.

`core/migrations.py` exists with an empty `MIGRATIONS` map, so the
infrastructure to handle this is present but unused.

Fix: bump to `"1.1"`, add `"1.1"` to `SUPPORTED_SCHEMA_VERSIONS`, and
register a `("1.0", "1.1")` migration that injects
`status="ok", error=None`. The four pre-existing files in `results/raw/`
are schema-1.0-without-status and will need it.

### 5.3 Test coverage does not reach the load-bearing logic — MAJOR

`tests/` contains two tests (`test_tokenizer.py`, `test_ollama_registry.py`),
both passing. One is a tiktoken round-trip; the other is marked
`@pytest.mark.integration` and hits a live Ollama with a hardcoded
`qwen3:4b`.

Nothing covers the logic that decides whether a run is valid or even starts:

- `kv_bytes_per_token` / `estimate_case_bytes` / `max_feasible_num_ctx`
  — the arithmetic that gates every run
- `_calculate_num_ctx` bucketing
- `_exceeds_context_limit` and the skip accounting
- `with_retries` retry predicate (especially the 404 decision)
- `_normalize_argv` shorthand rewriting
- `recommend_target_tokens` ladder selection
- health check status logic

All of these are pure functions over plain data and need no Ollama. The KV
formula in particular is a load-bearing published claim and should have a
test pinning it to the validated `qwen3:4b` figure (147,456 bytes/token).

`scripts/smoke_test.sh` covers the CLI surface at integration level but
requires a live daemon and an installed model.

### 5.4 Only one experiment exists — MINOR

`EXPERIMENTS` contains a single entry. `benchmarks/hallucination/` and
`evaluation/hallucination/` are empty package stubs. The `all` command and
the registry indirection are built for a plurality that does not yet exist.

### 5.5 Judge and embedding models bypass the memory plan — MINOR

`_check_memory_plan` only models the *generation* model. The judge model
(default: the same model at `num_ctx=4096`) and the embedding model are
additional resident memory that is never budgeted. On a 6 GB GPU this is the
difference between fitting and thrashing.

---

## 6. Dependency assumptions

- `ollama-python` must support the `think=` and `keep_alive=` parameters on
  `Client.chat`. Verified present in the installed version; older releases
  will raise `TypeError`.
- `tiktoken` downloads `cl100k_base` on first use. An offline machine fails
  the tokenizer health check unless `TIKTOKEN_CACHE_DIR` points at a warm
  cache.
- `pandas` is imported by `reporting/markdown.py`, which is currently dead
  code — the dependency is not otherwise required.

---

## 7. Priority for a publishable result

1. **1.1** tokenizer mismatch — invalidates the x-axis
2. **1.4** no repeats — no error bars
3. **1.3** no seed control — not reproducible
4. **1.2** self-judging — biased scores
5. **4.1** two-phase data loss — costs you long runs
6. **5.2** schema versioning — corrupts the result archive over time
7. **5.3** untested KV arithmetic — it is a load-bearing claim
