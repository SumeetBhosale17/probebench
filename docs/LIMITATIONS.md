# ProbeBench — Known Limitations

Status: as of 2026-08-29, branch `long-context-benchmark`.

This document records every limitation identified so far, with the reason it
exists and what would be needed to remove it. Sections 1 and 2 are the ones
that matter for publishable claims; the rest are engineering debt.

Companion documents: [JOURNAL.md](JOURNAL.md) (what we observed),
[DECISIONS.md](DECISIONS.md) (what we chose to do about it, and what we chose
against), [RESOLVED.md](RESOLVED.md) (limitations whose removal condition has
been met), [DESIGN.md](DESIGN.md) (how the system works now).

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
grading its own output.

This is not a mild self-preference bias. Run `0ca55bd787be` (JOURNAL J-006)
had `qwen3:0.6b` grade three of its own **correct** retrievals and returned
`0.0` twice, with reasons that named the expected string in the same clause
that called it missing:

> "The model response incorrectly states that the code is 'ALPHA-9921-X' but
> does not provide any relevant information about the text's content. The
> expected answer is missing, and the response is incomplete."

The third case returned `100.0` — the correct grade in the wrong unit — and
was rejected. The `llm_judge` column in a self-judged run measures the judge.

**Scope correction (JOURNAL J-009).** Those inverted grades turned out to be
mostly *prompt*-induced, not evidence of a model too small to judge. Holding
the judge model fixed at `qwen3:0.6b` and repairing only the prompt moves the
same responses from `0.0` to `0.99`/`1.00`, while a wrong code and a refusal
still score `0.0`. So this entry does **not** establish a judge-size floor —
that variable was never isolated. What survives is the structural point: a
model grading its own output is a self-evaluation bias, and its
`llm_judge` column is not reportable no matter how well it happens to score.

Consequence for the pivot: a failure corpus graded by a small self-judge has
corrupted ground truth *before* hand-labelling begins, which would invalidate
the precision/recall numbers the taxonomy is supposed to be validated
against.

Mitigation in place: the run logs a WARNING when the judge is the generation
model. Self-judging is also detectable in any archived record without a
schema change — `evaluation.judge.model == model.name`.

Fix: always pass an explicit, fixed `--judge-model` for reported results, and
state it — a model distinct from every system under test, ideally from a
different family. Whether a *minimum judge size* is additionally required is
an open question, not a settled one; see J-009.

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

### 1.5 `semantic_similarity` discriminates on response length, not correctness — MAJOR

Previously recorded here as "almost no discriminative power", on the evidence
that observed values were `1.0` and `0.9999999999999998`. Runs `0ca55bd787be`
and `b9fc2be30af6` contradict that: the metric spans 0.649 to 1.0 across four
responses that are **all fully correct** (JOURNAL J-007).

| predicted | semantic |
|---|---|
| `ALPHA-9921-X` | 1.000 |
| `The important secret mentioned in the text is ALPHA-9921-X.` | 0.795 |
| `The important secret ... is the access code, which is ALPHA-9921-X.` | 0.732 |
| `The important secret ... is the code **ALPHA-9921-X**. This code is tied to unlocking the door ...` | 0.649 |

`lexical_exact_match` is 1.0 for every row. The ordering is by word count.

Mechanism: `EmbeddingSemanticEvaluator` embeds the whole response and
cosine-compares it against `case.expected`, which is a bare 12-character
code. Every word of framing moves the response embedding away from it. The
class docstring already states it is a similarity metric and not a
correctness metric; the CLI summary table prints it beside
`lexical_exact_match` and `llm_judge` under a `context` axis, which reads as
correctness.

This is worse than no discriminative power. NIAH degradation is expected to
appear as longer, hedgier answers at depth — which this metric renders as a
falling curve **even if every answer stays correct**. That is a
publication-shaped result with no content behind it.

Fix: a decision, not a patch, because all three options change metric
semantics and break comparability with the archive. Either (a) drop it from
NIAH reporting, (b) redefine it as a maximum over the response's sentences,
so it asks "does any part of this response mean the expected answer", or
(c) keep it and rename it to something that cannot be read as correctness.
Whichever is chosen must be recorded as a metric-semantics change with a
version marker. **Open — no option selected yet.** The options and their
consequences are laid out in DECISIONS D-006, which adds a fourth (keep the
column but stop printing it in the summary table) and notes that no option
preserves the archived column's comparability.

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

### 1.12 The judge prompt is an unversioned measured variable — MAJOR

`JUDGE_SYSTEM_PROMPT` is a module-level string. Nothing records which version
of it graded a given run, and nothing bumps when it changes — yet J-009 shows
it dominated judge-model size on this task, moving the same judge from `0.0`
to `1.00` on the same responses.

Consequence: `llm_judge` values are only comparable within a single prompt
revision, and the record does not say which revision that was. Every
`llm_judge` value archived before 2026-08-31 was produced by the old
percentage-detour prompt and is not comparable with anything produced after.

This matters more after build-order step 5, which extends the same prompt
with a `label` field — classification labels would inherit the same silent
comparability break.

Fix: hash the judge system prompt and record it in `evaluation.judge`
(e.g. `prompt_sha256`), so a run states which judge contract produced its
scores. Deferred to the schema bump in build-order step 1 rather than taken
as a drive-by `to_record()` change (invariant 7).

**The prompt has now been revised twice on 2026-08-31** — once to remove the
percentage detour (R-003), once to add the groundedness contract (D-010).
The second revision moved `llm_judge` as well as adding a field: the
fabricated-justification response scored 1.00 under the score-only prompt and
0.95 with the groundedness section present, so the two fields are not as
independent as the prompt asserts. That is a small effect, but it means
`llm_judge` is not comparable across *either* revision, and nothing in the
record distinguishes the three prompt generations.

### 1.13 The `grounded` label is unvalidated, and needs a judge above an unknown floor — MAJOR

`grounded` (D-010) is a single boolean plus an evidence string, produced by
the judge and recorded in `evaluation_details.llm_judge`. Two things are not
established.

**Precision and recall are unmeasured.** J-010 ran it over the entire
archive: 44 records, **1 positive**, zero false positives. But 41 of those 44
predictions are bare code strings with no claim in them to be ungrounded
about, so the label is trivially `true` on them and carries no information.
The archive contains three informative records and one positive. n=1
establishes that the instrument fires on the case it was designed for; it
establishes nothing about how often it is right in general.

**There is a judge capacity floor and it is not located.** On a probe set of
seven responses, `qwen3:4b` scored 7/7 and `qwen3:0.6b` scored 1/7 — the
small model marked every response ungrounded except a bare code string. A run
judged below the floor does not merely miss failures, it **manufactures**
them, reporting `grounded: false` on nearly everything. Nothing currently
detects this.

Consequence: `grounded` must not be aggregated into a rate, or cited as
evidence about a model, until a failure corpus exists and per-label precision
and recall are measured against hand-labelled ground truth.

Fix: build-order step 2 (make failures exist), then hand-label a sample and
report precision/recall per label. Locating the judge floor needs the same
corpus. Until then the field is diagnostic evidence for reading case by case,
not a statistic.

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
2. **1.5** `semantic_similarity` tracks length — can manufacture a falling
   context-length curve out of correct answers
3. **1.4** no repeats — no error bars
4. **1.3** no seed control — not reproducible
5. **1.2** self-judging — biased scores
6. **1.12** unversioned judge prompt — `llm_judge` not comparable across runs
7. **4.1** two-phase data loss — costs you long runs
8. **5.2** schema versioning — corrupts the result archive over time
9. **5.3** untested KV arithmetic — it is a load-bearing claim

1.5 is placed second because it is the only entry here that can produce a
*plausible-looking* result rather than a missing or noisy one.
