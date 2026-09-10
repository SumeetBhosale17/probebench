# ProbeBench — Findings and Implementation Notes

Status: as of 2026-08-29, branch `long-context-benchmark`.

This document records the two production failures that motivated the current
architecture, their root-cause analysis, and what was built in response —
what each change does, how it works, and why it was necessary.

Companion document: [LIMITATIONS.md](LIMITATIONS.md).

---

## 1. The two failures

### 1.1 Failure A — KV cache allocation failure at 256k context

```
ollama._types.ResponseError: llama-server process has terminated: exit status 1:
ggml_aligned_malloc: insufficient memory (attempted to allocate 36000.00 MB)
alloc_tensor_range: failed to allocate CPU buffer of size 37748736000
llama_init_from_model: failed to initialize the context:
    failed to allocate buffer for kv cache (status code: 500)
```

Host: 23 GiB RAM (≈14 GiB free), RTX 3050 Laptop 4 GiB VRAM, **zero swap**.
Model: `qwen3:4b`. Requested context: 256,000 tokens.

### 1.2 Failure B — HTTP 404 mid-run on a shared machine

```
ollama._types.ResponseError: model 'qwen3:8b' not found (status code: 404)
```

Host: `pc-13@ProjectLab-13`, RTX 3050 6 GB, models `llama3.1:8b` and
`qwen3:8b`. The run completed cases 1 and 2 normally, then failed at case 3
— inside the **judge** call, not generation. A second run with
`generation=llama3.1:8b, judge=qwen3:8b` failed the same way.

---

## 2. Root-cause analysis

### 2.1 Failure A: the KV cache scales linearly with context, and nobody checked

A transformer's KV cache holds a key and a value vector per layer per token:

```
kv_bytes_per_token = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element
```

For `qwen3:4b` (36 layers, 8 KV heads via GQA, head_dim 128, f16):

```
2 × 36 × 8 × 128 × 2 = 147,456 bytes/token = 144 KiB/token
147,456 × 256,000    = 37,748,736,000 bytes = 36,000 MiB
```

This matches the reported allocation **exactly**. The failure was not a bug
in ProbeBench; it was an unbudgeted 35 GiB request on a machine with 14 GiB
free and no swap to degrade into.

The guard that existed (`run.py`) compared the requested window against
`model_info.context_length` — 256,000 < 262,144, so it passed. **The gap was
conceptual**: "the architecture supports this context" and "this machine can
afford this context" are different questions, and only the first was being
asked.

### 2.2 Failure B: runner thrash, and a model store that moved

The 404 landed on the judge call specifically, and that is diagnostic.

Ollama keys a `llama-server` runner on `(model, num_ctx, …)`. Generation
passed a per-case `num_ctx`; the judge passed `options={"temperature": 0}`
with **no `num_ctx`**. Those are two different runners. With `qwen3:8b` at
Q4 (~5.2 GB) on a 6 GB card, they cannot coexist, so every case did:

```
load gen runner → generate → EVICT → load judge runner → judge → EVICT → …
```

≈5 GB of load/unload churn, twice per case, 40 times over a 20-case run.

That explains the *pressure*. It does not by itself explain a 404, which
means "name not resolvable in the manifest store" — a model that answered
three requests cannot have ceased to exist. The conclusion is that **the
server's view of its model store changed mid-run**. The leading explanation
is the shared-machine trap: a user-launched `ollama serve` and a systemd
`ollama` service use different model directories and both bind `:11434`. If
the foreground server is OOM-killed during a 5 GB reload and the service
takes the port, every later request hits a different — possibly empty —
store.

This was diagnosed but **never confirmed on that host** (see
LIMITATIONS §4.6). The engineering response was therefore twofold: remove
the thrash that creates the pressure, and fail fast with an actionable
message rather than dying at case 3.

---

## 3. What was built

### 3.1 Memory preflight — `core/preflight.py`

**What.** Predicts the memory cost of every planned context size and refuses
the run if it will not fit, before any model is loaded.

**How.** `ModelInfo` gained the GGUF fields needed to compute KV cost
(`block_count`, `kv_head_count`, `head_dim`, `size_bytes`), extracted in
`OllamaModelRegistry.inspect()` via a suffix matcher (`_find_int`) because
GGUF keys are architecture-prefixed (`qwen3.block_count`,
`llama.attention.head_count_kv`). `kv_bytes_per_token()` applies the formula
in §2.1. `check_memory_budget()` compares `weights + KV + 10% compute buffer`
against `(free RAM + free VRAM) × 0.85`.

**Why.** This is the direct fix for Failure A. The formula is exact for the
KV term and was validated against the observed 36,000 MB.

Beyond blocking failures, it enables two things the project needs:
- `max_feasible_num_ctx()` solves the budget equation for the largest
  affordable context, rather than searching.
- `recommend_target_tokens()` selects the feasible rungs of a standard
  ladder, which is what `--profile auto` consumes.

### 3.2 Two-phase execution — `core/runner.py`, `experiments/pipeline.py`

**What.** All generations run first; all evaluations run second.

**How.** `BenchmarkRunner.run_case` was split into `generate()` and
`evaluate()`. `_run_two_phase` drives them in separate loops. It lived in
NIAH's runner until D-021 moved it to `experiments/pipeline.py`, where all
three experiments share one copy.

**Why.** This is the direct fix for Failure B's thrash. Single-phase
alternation forces `2N` model swaps for N cases; two-phase forces two, one
per phase.

Measured on `qwen3:4b`, 2 cases at 4k context: evaluation of case 1 took
5.7 s (judge cold-loading), case 2 took **1.7 s** — the judge runner stayed
resident. The gap widens with case count and context size.

**Cost.** Nothing is written to disk until phase 1 completes
(LIMITATIONS §4.1). `--single-phase` remains available and is the safer
choice for very long runs until checkpointing is added.

### 3.3 Judge context pinning — `evaluation/.../judge/judge.py`

**What.** The judge always requests the same `num_ctx` (default 4,096),
disables thinking, and truncates the graded response.

**How.** `options={"temperature": 0, "num_ctx": self.num_ctx}` plus
`think=False` and `_truncate()`.

**Why.**
- **Pinning `num_ctx`** keeps the judge on one runner for the whole run.
  Without it, Ollama spawns a fresh judge runner for every *distinct
  generation* `num_ctx`, which is the mechanism behind Failure B.
- **`think=False`** — `qwen3` advertises the `thinking` capability. Grading
  is a classification task; reasoning tokens are pure latency.
- **Truncation** is required *because* of the pinning: a model that echoes
  its haystack would otherwise overflow 4,096 tokens and silently push the
  grading rubric out of context.

### 3.3a The judge emits a score *and* a label — `evaluation/.../judge/`

**What.** One judge call answers two independent questions: `score`, a float
in [0.0, 1.0] that flows to `metrics`, and `grounded`, a boolean that flows
to `evaluation_details.llm_judge` alongside the `unsupported_claim` that
evidences it. See D-010.

**How.** `build_judge_system_prompt(with_groundedness=...)` composes the
contract from a scoring section and an optional groundedness section, so the
scoring half exists once rather than in two copies that drift.
`build_judge_prompt(..., source=...)` supplies the needle as the SOURCE
SENTENCE. `OllamaJudge` reads it from `case.metadata["needle"]`; a case
without one is scored but not grounded-checked, and the source block is
omitted rather than passed empty.

**Why.**
- **The needle, not the haystack, is the reference.** It is the only thing
  in the prompt that licenses a claim about the answer, so a claim absent
  from it is invented — even when its vocabulary appears in the filler.
  ("door" occurs 333 times in *War and Peace*; that does not ground
  "this code unlocks the door".)
- **A label, not a fourth float.** D-007 rejected compressing a *kind* of
  failure into a magnitude. `grounded` stays out of `metrics` specifically
  so it cannot be averaged — a "mean groundedness of 0.97" destroys the
  information the field exists to carry.
- **No second model call.** The judge call is already the expensive one on a
  memory-bound host, and a second per-case call would reintroduce exactly the
  runner pressure invariant 3 exists to prevent (D-008).
- **Absent, never defaulted.** A missing or non-boolean `grounded` leaves the
  key out entirely rather than defaulting to `true` — invariant 8 applied to
  this field. A bad label invalidates only the label; the score still records.

**Caveat.** The field is unvalidated (LIMITATIONS §1.13): one positive in the
whole archive, and a judge capacity floor that is known to exist but not
located.

### 3.4 `num_ctx` bucketing — `benchmarks/long_range_dependency/*/benchmark.py`

**What.** `num_ctx` is rounded up to a 512-token boundary.

**Why.** Discovered during verification: a 16,000-token target produced
`num_ctx` of both `16,511` and `16,512` across depths, because the haystack
builder lands on slightly different token counts. J-030 later found the
mechanism: splicing tokens produces a non-canonical sequence, so the served
text re-encodes 0 or 1 tokens shorter, depth-dependently (§1.19). A one-token
difference spawns a **separate `llama-server`**. Bucketing collapsed a
25-case run from 6 distinct runners to 5, and guarantees all cases at one
target size share one.

### 3.5 Failure isolation — `core/runner.py`, `core/result.py`

**What.** A failed generation or evaluator records an error and the run
continues. `BenchmarkResult` gained `status` (`ok` / `generation_error` /
`evaluation_error`) and `error`.

**How.** Generation and each evaluator are individually wrapped;
`--fail-fast` restores abort-on-first-failure.

**Why.** Failure B destroyed 2 completed cases out of 20 because one judge
call raised. Verified: pointing `--judge-model` at `nomic-embed-text`
(which cannot chat) now yields `status=evaluation_error`, the run completes,
and the error text is preserved in `evaluation_details`.

**Key design decision.** A failed evaluator leaves its metric **absent from
`metrics`, not `0.0`**. A judge that errored is missing data; scoring it zero
would silently bias every aggregate downward. The consequence — differing
denominators per metric — is documented in LIMITATIONS §1.7.

### 3.6 Retries — `core/retry.py`

**What.** Transient Ollama failures are retried with exponential backoff.

**How.** `with_retries()` retries on `{404, 500, 502, 503, 504}` and on
httpx timeout/connect/protocol errors. Non-retryable statuses (e.g. 400
"does not support chat") raise immediately.

**Why 404 is retryable.** On a thrashing host, Ollama can transiently fail
to resolve a model it is mid-unload. A genuinely absent model is caught by
`ensure_availability()` before the run starts, so a 404 *during* a run is
more likely transient than real. This is a deliberate heuristic, not an
oversight — see LIMITATIONS §4.2.

### 3.7 Health checks — `core/health.py`

**What.** Seven environment checks run before every benchmark: Ollama
reachability, model-store identification, system memory, benchmark data
files, tokenizer loading, output directory writability, required models.

**Why each one exists** — every check corresponds to an observed or
anticipated failure:

| Check | Failure it prevents |
|---|---|
| Ollama daemon | connection errors surfacing as tracebacks mid-run |
| Model store | Failure B's leading hypothesis — warns when two stores exist |
| System memory | context sizes the host cannot hold; flags zero swap |
| Benchmark data | running outside the repo root (paths are relative) |
| Tokenizer | `tiktoken` downloads its encoding on first use; fails offline |
| Output directory | discovering unwritable output after hours of compute |
| Required models | Failure B's symptom — a missing model, caught at t=0 |

The model-store check queries `systemctl show ollama --property=Environment`
rather than guessing paths, because distributions disagree
(`/var/lib/ollama` on Arch, `/usr/share/ollama/.ollama` on Debian).

### 3.8 Model installation — `models/installer.py`

**What.** Missing models are offered for download.

**How.** `confirm_install()` prompts; `--yes` pre-authorises; a
**non-interactive shell refuses**.

**Why the refusal matters.** Pulling a model is a multi-gigabyte network
download. An unattended or CI run must not start one on an implicit
decision. Verified: `probebench doctor tinyllama < /dev/null` exits 1 without
downloading.

### 3.9 CLI ergonomics — `cli.py`, `experiments/registry.py`

**What.** `probebench <model>` runs every registered experiment.

**How.** `_normalize_argv()` rewrites a bare first argument to
`all <model>`. `ExperimentSpec` entries in `experiments/registry.py` carry
the runner, data-file requirements, and description; `all`, `doctor` and the
health check all read from that list.

**Why.** Adding an experiment should be one registry entry, not edits across
the CLI, the health check, and the runner. The shorthand exists because the
full form is long enough to discourage routine use.

New diagnostic commands:
- `probebench doctor [model]` — environment report, exit 1 on failure
- `probebench plan <model>` — per-context memory table and recommended sweep
- `probebench models pull <model>` — explicit installation

### 3.10 Bugs found in pre-existing code

Found while integrating, all verified:

| Location | Bug | Effect |
|---|---|---|
| `cli.py` | `action="store-true"` (hyphen) | argparse raised at parser construction — **every command was broken** |
| `registry.py` | `head_dim = embedding_length / head_count` | float division produced float byte counts |
| `registry.py` | `block_count`/`kv_head_count`/`size_bytes` computed but not passed to `ModelInfo` | **memory preflight silently no-opped** |
| `registry.py` | `list_models()` never set `size_bytes` | same |
| `health.py` | remedy text told the user to set `OLLAMA_HOST`, which the code ignored | misleading; fixed by adding `models/host.py` |

The two `registry.py` field-wiring bugs are the instructive ones: the
preflight *appeared* to work while doing nothing, because
`kv_bytes_per_token()` returns `None` when geometry is missing and
`check_memory_budget` treats `None` as "skip". A silent no-op is the worst
failure mode for a safety check.

### 3.11 Content-addressed case identity — `core/case_identity.py`, `*/identity.py`

**What.** Two keys per case. `case_key` is the design point
(`niah/t4000/d0.50/n06bfb731/marked/g0`); `case_fingerprint` is a digest over
everything determining the model's input.

**How.** Canonical JSON — sorted keys, no whitespace — with
`FINGERPRINT_VERSION` hashed *inside* the digest, so "the input changed" is
distinguishable from "we started hashing one more thing". Raw floats are
**refused**: `0.1 + 0.2` and `0.3` would hash differently, so depths go through
`format_depth()` and arrive as strings.

**Why.** `case_id` is `niah_{target}_{depth}_{counter:04d}`, and the counter runs
over the whole sweep — it shifts when `--needles` changes or a cell is skipped
(J-004). Cross-model joins on it are unsound. Hardware is deliberately *not* a
component: the machine does not change the model's input, and including it would
stop the same case joining across machines, which is the comparison D-013 exists
to enable.

Each family declares its own components; `core/` only decides how a component set
is serialised. That is what stops two families quietly disagreeing about it.

**Validated.** 166 archived records rebuild their stored fingerprint end to end,
through the generator, the prompt assembly and the component set. A live 2-case
run joined the archive 2 of 2 after the k-block refactor.

### 3.12 Measured KV precision — `core/kvprobe.py`

**What.** The server's actual KV cache precision, measured rather than assumed.

**How.** `/api/ps` reports each loaded model's `size` and the `context_length` it
loaded at. Since `size = weights + buffers + kv_bytes_per_token · num_ctx` and
only the last term depends on context, loading the same model twice at two
context sizes and differencing cancels everything else exactly:

```
kv_bytes_per_token = (size_b − size_a) / (ctx_b − ctx_a)
bytes_per_element  = kv_bytes_per_token / (2 · n_layers · n_kv_heads · head_dim)
```

**Why.** `--kv-cache-type` only ever configured our own *estimator* (J-016). The
real setting lives in `OLLAMA_KV_CACHE_TYPE` in a systemd daemon running as
another user, whose `/proc/PID/environ` is unreadable (J-018). Asking our own
shell answers a question about the wrong process. So this uses R-001's arithmetic
as a *measuring instrument* rather than a predictor, and it works remotely.

Two calibrations were paid for in J-026 and J-028. ggml quantises in blocks of 32
values plus an fp16 scale, so `q8_0` costs **34/32 = 1.0625** bytes/element, not
1.0 — using the nominal width rejected a correct reading of 1.19 as unrecognised.
And Ollama *clamps* a requested `num_ctx` to the model's window and reports the
clamped value, so the probe must know the ceiling or it matches nothing.

A mismatch between measured and requested **refuses the run**: archiving a
mislabelled record is worse than not running. It caught a live misconfiguration
before it produced 540 bad records (J-025).

### 3.13 Instruction compliance — `evaluation/.../compliance.py`

**What.** Did the response obey "answer ONLY with the code"? Binary, offline,
free.

**How.** `classify_form()` normalises markup, quotes and trailing punctuation and
returns `exact | stripped | prose | empty`. It scores **FORM** and never reads
`expected`.

**Why that restriction matters.** Defining compliance as "equals the expected
string" makes it a strictly stronger `lexical_exact_match` — every compliant
response is correct by construction, the "obeyed the format but retrieved the
wrong code" cell becomes *unreachable* rather than merely unobserved, and the
2×2 collapses algebraically to its second term. J-022 confirmed the cell was
empty across 424 NIAH records, which is precisely why the better-defined rule
cost nothing to adopt — and J-032 then found **5 cases in it**, which the
value-based definition could never have surfaced.

Born with a `RULE_VERSION`, which is the one thing `lexical_exact_match` cannot
do: three definitions share two names in the archive and nothing says which
produced a given value (D-014).

### 3.14 The k-block haystack primitive — `benchmarks/long_range_dependency/haystack.py`

**What.** Splice *k* blocks into a token-controlled filler body at *k* depths,
returning the text **plus a full inventory** of what was planted and where.

**How.** Depths are computed against the **original** body, then the document is
assembled by segment rather than spliced in place — nothing is mutated, so no
index can be invalidated. Realised depth is computed after placement, because
the denominator is not known until every block is placed.

**Why depths against the original body.** The lesser reason is that depths stay
independent and comparable across *k*. The real one: it holds the filler
*content* at each insertion site identical across every cell of the grid. §1.9
measured the filler as a semantic distractor, so which Tolstoy passage neighbours
a needle is a first-order variable — depths against a growing body would slide
every later site and change that neighbour as a side effect of *k*, confounding
the distractor axis with the filler-neighbourhood axis.

**Why collisions raise.** Two repairs are available and both corrupt the
measurement. Dropping a colliding block varies *k* across cells and confounds
depth with difficulty; shifting one perturbs the background in exactly the cells
where the target is nearest a distractor, which is where the signal is. Callers
choose depths that interleave — the target sweeps tenths, the background sits on
sixteenths — which makes the branch unreachable for every documented grid.

**Cost.** The single-needle path had to stay byte-identical: 590 archived records
join on `case_fingerprint`, which hashes `prompt_sha256`, so one changed byte
would stop the archive matching anything run afterwards. Guarded three ways —
three pinned digests, an independent reference implementation of the pre-refactor
algorithm over the full grid, and the 166-record replay.

### 3.15 The shared experiment pipeline — `experiments/pipeline.py`

**What.** Everything that is not family-specific: run id, output path, model
inspection, host provenance, KV probe, case build, memory plan, two-phase
execution, summary.

**How.** An experiment supplies an `ExperimentPlug` — build cases, build
evaluators, and whether an embedding model must be present. NIAH's runner went
from 485 lines to 119.

**Why.** The ordering in it is *knowledge*, not arrangement, and most of it was
paid for with production failures: the KV probe runs before case generation so it
cannot evict the sweep's runner (invariant 3), the memory plan runs before any
model call (invariant 2), generation and evaluation are separate phases (R-002).
Three copies of that ordering would be two chances to regress it silently.

**One thing the extraction broke, and how.** The log file handler was attached to
the NIAH runner's **own module logger**. After the split, the pipeline's messages
and each family's messages live on *sibling* loggers — so the self-judging
warning that §1.2 depends on being visible would have been written to no file at
all, and nothing errors when a log record has no handler. Fixed by attaching to
the `probebench` package logger, which is what a run log should always have
captured. **Generalisable: extracting a module splits a logger hierarchy, and the
failure mode is silence.**

### 3.16 Three experiments on one primitive — `NIAH`, `NIAH_distractor`, `NIAH_multihop`

**What.** Retrieval, discrimination, and composition — the same corpus, the same
marker, the same lengths, three different tasks.

| | NIAH | NIAH_distractor | NIAH_multihop |
|---|---|---|---|
| Planted | 1 needle | 1 target + k decoys | 1 pointer + k registry entries |
| Asks | "the important secret" | "the code for {subject}" | "the code for {pointer}" |
| Task | retrieval | discrimination | **composition** |
| Answer reachable in | 1 lookup | 1 lookup + discrimination | **2 lookups** |

**How the keyed families avoid §1.9.** One template, `The access code for
{subject} is {value}.`, twelve subjects. Every needle is **exactly 15 tokens**,
one value shape, distinct leading characters, none occurring in *War and Peace* —
asserted by test, because "uniform" is a property of a data file and data files
drift. Only the subject distinguishes two needles, so a wrong answer equal to a
planted code is *necessarily* a discrimination failure.

**Why that is not free.** Uniform wording deletes the 19-point variable §1.9
measured *by construction*, so distractor accuracy is **not comparable** with
NIAH accuracy. The k=0 cell is the one bridge: NIAH's structure with only the
wording changed, which turns the delta into a measured quantity instead of an
assumption (D-023). It bridges exactly one of the four differences — see §1.20.

**Why multi-hop has no k=0 or k=1 cell.** With one registry entry the only code
in the text is the answer, so returning it proves nothing about composing two
hops. The decoys *are* the experiment. And the pointer deliberately carries no
value: putting the answer in it would let a single-hop read score as a two-hop
one.

---

## 4. Verification evidence

All measured on EndeavourOS, 23 GiB RAM, RTX 3050 Laptop 4 GiB, `qwen3:4b`.

| Claim | Evidence |
|---|---|
| KV formula is correct | `plan` reports 35.2 GiB at 256,512 ctx; observed llama.cpp error was 36,000 MB |
| Preflight blocks Failure A | `--target-tokens 256000 --dry-run` → exit 1, "Insufficient memory", no model call |
| Two-phase keeps the judge resident | eval times 5.7 s → 1.7 s between case 1 and case 2 |
| Bucketing collapses runners | 25 cases across `[4608, 8704, 16896, 32768, 64512]`, was 6 distinct values |
| Failure isolation works | `--judge-model nomic-embed-text` → `status=evaluation_error`, run completes, `llm_judge` absent from `metrics` |
| Non-retryable errors don't waste retries | HTTP 400 "does not support chat" raised immediately |
| Missing models fail fast | `doctor mistral:7b` → exit 1 at startup, not mid-run |
| Non-interactive refuses downloads | `doctor tinyllama < /dev/null` → exit 1, nothing pulled |
| CLI surface is sound | `scripts/smoke_test.sh` — 16/16 |
| Full pipeline | 2-case run: all three metrics 1.0, `status=ok` |
| KV probe reads the real precision | 1.06 B/element measured → `q8_0`; caught a daemon override that had silently applied nothing (J-025) |
| Case identity survives construction change | 166 archived fingerprints rebuild through the generator + prompt assembly; a fresh run joined the archive 2/2 after the k-block refactor |
| Single-needle path is byte-identical | 3 pinned digests + an independent reference implementation over 168 grid points + the 166-record replay |
| Compliance separates from retrieval | J-032: 5 of 50 cases are bare-and-wrong — the 2×2 cell empty across 424 NIAH records |
| Multi-hop produces real failures | 16 of 50 at 4,000 tokens, two modes, classified offline from the stored inventory with no model call |

---

## 5. Notes for the paper

Points from this work that are worth stating explicitly in a methods or
threats-to-validity section:

1. **Hardware feasibility is a first-class experimental constraint.** The
   advertised context window of a model (262,144 for `qwen3:4b`) is not the
   context window that can be benchmarked on a given host (≈88,800 tokens on
   the reference machine). Any claim about long-context behaviour must state
   the host's memory budget, because it bounds what was measurable.

2. **KV cache cost is predictable and should be reported.** The formula in
   §2.1 gives the exact per-token cost from GGUF metadata. Reporting
   KiB/token alongside results lets readers reproduce the feasibility
   envelope.

3. **Serving-layer artefacts contaminate timing measurements.** Latency
   figures from a single-phase harness on a memory-constrained host measure
   model loading, not inference. The two-phase design exists specifically to
   remove that confound. Latency numbers should state which mode produced
   them.

4. **Evaluator failures must be distinguished from evaluator zeros.** This
   is a small design choice with real statistical consequences, and the
   convention used should be stated.

5. **The tokenizer mismatch (LIMITATIONS §1.1) is currently the single
   largest threat to validity** and should be resolved before any
   cross-model context-length claim is published.

6. **A saturated benchmark is measuring its own ceiling, not the model.**
   Every metric on every successful NIAH case in a 590-record archive is
   exactly 1.0. The fix that worked was not a longer context or a weaker model
   — both make the task *harder* without making it *different*. Changing the
   task's structure (one pointer indirection) produced a 32% failure rate at
   the shortest length in the grid. Report the structure of the task, not only
   its size.

7. **Three tasks that share a corpus, a marker and a length are still three
   tasks.** `NIAH`, `NIAH_distractor` and `NIAH_multihop` emit identical metric
   names over identical inputs and are not comparable on any axis (§1.20).
   Any cross-family figure must be faceted or must state which of the four
   differences it holds fixed. The similarity of the output is the hazard.

8. **Synthetic benchmarks should record what they constructed, not only what
   they expect.** Because we build the haystack, the failure taxonomy is
   largely decidable by substring search over a known inventory — no judge, no
   second model call, and re-runnable over stored results when the rules
   change. Storing only the expected answer discards that. This is the single
   cheapest thing in the project and it is what made J-032's two-mode split a
   regex rather than a labelling exercise.

9. **Report *n* next to any failure-mode claim.** A conclusion drawn from six
   cases in this project was overturned by fifty the same day (J-031 → J-032):
   `niah.distractor_retrieval` fired 0/6, then 7/16. Both entries are kept.
