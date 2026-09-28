# ProbeBench — Resolved Limitations

What was wrong, what we did about it, and **why the fix is correct rather
than merely effective**.

Companion documents: [LIMITATIONS.md](LIMITATIONS.md) (what is still wrong),
[JOURNAL.md](JOURNAL.md) (what we observed and when),
[DECISIONS.md](DECISIONS.md) (what we chose, and against what),
[DESIGN.md](DESIGN.md) (how the system works now).

---

## Why this file exists

LIMITATIONS.md is a list of open problems; entries leave it when they are
fixed. DESIGN.md describes the system as it stands, in the present tense. So
between them, the *reasoning that produced a fix* has nowhere to live — and
that reasoning is the part that is hard to reconstruct and easy to lose.

A year from now, "why is there a memory preflight?" is answerable from
DESIGN.md. **"Why a predictive arithmetic model rather than catching the
allocation error and retrying smaller?"** is not. That second question is
what this file answers, and it is the one that matters when the next
limitation looks superficially similar.

This file is also the honest record of *method*. Some fixes here were reached
by a clean experiment; at least one was reached after a confounded control
sent us to the wrong conclusion first (R-003). Recording which is which is
what stops the same mistake being repeated.

## When to write an entry

Write one when a limitation's **stated removal condition is met** — not when
a fix is applied and looks like it works, and not when a problem stops being
visible. Concretely, all three must hold:

1. The mechanism is understood, not just the symptom suppressed.
2. There is validation: a command, an arithmetic check, or a measurement
   that would fail if the fix regressed.
3. The residual is stated — what the fix does *not* cover.

If a fix works and you cannot say why, that is a JOURNAL entry
(`Mechanism: unknown`), not a RESOLVED entry.

## Relationship to the other documents

| Event | Where it goes |
|---|---|
| Something surprising happened | JOURNAL.md, **before** the fix (invariant 12) |
| It threatens a claim | LIMITATIONS.md, with severity + removal condition |
| A choice was made between options | DECISIONS.md, **before** the change lands (invariant 13) |
| The removal condition is now met | **here**, and the LIMITATIONS entry is struck |
| The system's behaviour changed | DESIGN.md what/how/why |

Where a DECISIONS entry exists, this file's **Decision** section is a pointer
to it (`see D-00n`) plus what was learned since — not a second copy of the
argument. The D entry records what was believed *before* the outcome was
known; that is what makes it worth keeping separately. R-001, R-002 and R-003
predate the file, so they carry their reasoning in full and are cross-linked
from D-001, D-002 and D-005 respectively.

Removing an entry from LIMITATIONS.md without adding one here is what this
file exists to prevent. A limitation that quietly disappears is
indistinguishable from one that was forgotten.

## Entry format

```markdown
## R-00n — <title>
Resolved: <date> | Was: <LIMITATIONS §x, JOURNAL J-00n> | Code: <path>

**The limitation.**  What was actually wrong. Raw evidence where it exists.
**Methodology.**     How it was investigated. The steps that found the answer,
                     including the ones that were wrong.
**Decision.**        What was chosen — and what was rejected, with the reason.
**Why it works.**    The mechanism. Not "it stopped happening".
**How we know.**     Validation that would fail if the fix regressed.
**Residual.**        What this does not cover.
```

---

# Entries

## R-001 — Unbudgeted KV cache allocation crashed the run
Resolved: 2025-08-19 | Was: JOURNAL J-001, DESIGN §1.1/§2.1/§3.1 | Code: `core/preflight.py`

**The limitation.** Requesting a 256,000-token context on a 14 GiB-free
machine killed the Ollama runner and took the entire run with it:

```
ggml_aligned_malloc: insufficient memory (attempted to allocate 36000.00 MB)
alloc_tensor_range: failed to allocate CPU buffer of size 37748736000
llama_init_from_model: failed to initialize the context:
    failed to allocate buffer for kv cache (status code: 500)
```

The guard that existed compared the requested window against the model's
advertised `context_length` — 256,000 < 262,144, so it passed. The gap was
conceptual: *"the architecture supports this context"* and *"this machine can
afford this context"* are different questions, and only the first was being
asked.

**Methodology.** The raw allocation figure was kept before anything was
changed — which is the only reason the rest was possible. `36000.00 MB` was
checked against the standard KV-cache identity:

```
kv_bytes_per_token = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element
2 × 36 × 8 × 128 × 2 = 147,456 bytes/token = 144 KiB/token
147,456 × 256,000    = 37,748,736,000 bytes = 36,000 MiB
```

An **exact** match, not an approximation. That single check converted a crash
into a validated model: if the arithmetic reproduces the failure to the byte,
it can also predict which contexts will fail *before* they are attempted.

**Decision.** Compute the requirement ahead of the call and refuse
infeasible cases — rather than the two obvious alternatives.

*Rejected: catch the 500 and retry at a smaller context.* It treats a
predictable quantity as a surprise. The allocation is a closed-form function
of published model geometry; discovering it by crashing wastes the model
load, and on a machine with no swap the failure mode is not always a clean
exception.

*Rejected: a fixed context ceiling per machine.* It would be wrong for every
model, since the per-token cost varies by an order of magnitude with layer
count, KV heads, and cache precision.

**Why it works.** The KV cache is the dominant *variable* memory cost, and it
is linear in context length with a constant that is fully determined by
metadata available before inference: `n_layers`, `n_kv_heads`, `head_dim`,
and bytes per element. Nothing about it is emergent or workload-dependent.
So the feasible context set is computable, not discoverable — and a
prediction that reproduces a real failure exactly is a prediction, not a
heuristic.

The geometry comes from GGUF metadata via `OllamaModelRegistry.inspect()`.
Keys are architecture-prefixed (`qwen3.block_count`), so a suffix matcher
(`_find_int`) is used rather than literal keys — otherwise every new model
family would silently fall back to a default and the guard would quietly
stop guarding.

**How we know.** The formula reproduces the observed 36,000 MiB allocation
exactly. `uv run probebench plan <model>` prints the feasible contexts for
the current host, and `uv run probebench models inspect <model>` reports KV
cache per token. Invariant 2 — never call a model without a memory preflight
— makes bypassing it a deliberate act (`--skip-memory-check`).

**Residual.** The estimate is an approximation of *total* memory, not an
allocation trace: it models the KV cache and not compute buffers, CUDA
context, or fragmentation (LIMITATIONS §2.1). The budget is a snapshot of
free memory at preflight time and can be invalidated by another process
(§2.2). Non-NVIDIA GPUs are invisible (§2.3) and detection is Linux-only
(§2.4). The arithmetic itself is still not unit-tested (§5.3) — a
load-bearing claim without a regression test.

---

## R-002 — Runner thrash: the judge evicted the generation model every case
Resolved: 2025-08-19 | Was: JOURNAL J-002, DESIGN §1.2/§2.2/§3.3/§3.4 | Code: `evaluation/.../judge/judge.py`, `benchmarks/.../benchmark.py`

**The limitation.** A run failed at case 3 with a 404 for a model that had
already answered twice:

```
ollama._types.ResponseError: model 'qwen3:8b' not found (status code: 404)
```

**Methodology.** The diagnostic detail was *where* it landed: inside the
judge call, not generation. That located the mechanism. Ollama keys a
`llama-server` runner on `(model, num_ctx, …)`. Generation passed a per-case
`num_ctx`; the judge passed `options={"temperature": 0}` with **no
`num_ctx`**. Those are two different runners, and at ~5.2 GB on a 6 GB card
they cannot coexist:

```
load gen runner → generate → EVICT → load judge runner → judge → EVICT → …
```

≈5 GB of load/unload churn, twice per case, 40 times over a 20-case run.

A second effect was found during verification rather than by reasoning: a
16,000-token target produced `num_ctx` values of both `16,511` and `16,512`
across depths, because `create_haystack` lands on slightly different token
counts. **A one-token difference spawns a separate `llama-server`.**

**Decision.** Pin the judge's `num_ctx` to a constant, and round generation's
`num_ctx` up to a 512-token boundary.

*Rejected: serialising phases to avoid coexistence.* Two-phase execution was
adopted for other reasons, but it does not fix this — the judge would still
spawn a new runner per distinct generation `num_ctx`.

*Rejected: treating the 404 as the bug and retrying it.* 404 means "name not
resolvable in the manifest store", and a model that answered three requests
cannot have ceased to exist. Retrying would paper over a store that changed
underneath the server.

**Why it works.** Both changes attack runner *identity*, which is the actual
key. Pinning collapses every judge call in a run onto one runner. Bucketing
collapses every case at one target size onto one generation runner — it took
a 25-case run from 6 distinct runners to 5, and guarantees all depths at a
given size share one. Together they remove the churn that created the memory
pressure, instead of handling its symptom.

Pinning forces a second change that is easy to miss: the graded response must
be truncated (`_truncate`, 4,000 chars), because a model that echoes its
haystack would otherwise overflow the pinned 4,096-token window and silently
push the grading rubric out of context. The fix is only safe *with* the
truncation, which is why invariant 3 names the pinning specifically.

**How we know.** Runner counts were observed to drop as described.
Invariant 3 states the pinning is non-negotiable, and DESIGN §3.3 records
why, so an unpinned judge is a visible violation rather than a silent
regression.

**Residual.** **The 404's root cause was never confirmed on that host**
(LIMITATIONS §4.6). The leading explanation — a user-launched `ollama serve`
and a systemd `ollama` service using different model directories while both
binding `:11434` — is consistent with the evidence but untested. What was
fixed is the *pressure* that triggered it, plus failing fast with an
actionable message. That is a mitigation of a diagnosed-but-unconfirmed
cause, and it is listed here as resolved only because the runner thrash
itself was measured and removed. Truncation is still not recorded in
`evaluation_details` (§1.11).

---

## R-003 — The judge returned `100.0`, and graded correct answers `0.0`
Resolved: 2026-08-31 | Was: JOURNAL J-006, J-009; LIMITATIONS §1.2 | Code: `evaluation/.../judge/prompt.py`, `judge/judge.py`

**The limitation.** One case aborted its judge evaluation outright:

```
ValueError: Evaluation score must be in [0.0, 1.0], got 100.0.
```

and two others, whose responses contained the expected code verbatim, were
graded `0.0` with self-refuting reasons:

> "The model response incorrectly states that the code is 'ALPHA-9921-X' but
> does not provide any relevant information about the text's content. The
> expected answer is missing, and the response is incomplete."

**Methodology — including the part that went wrong.** The prompt asked the
judge to "score the response as a percentage from 0 to 100 ... then report
that percentage divided by 100", and restated every rubric band in both units
(`1.0 (100%)`, `0.0 (0%)`). That explains the `100.0` immediately: a two-step
unit conversion, of which a small model performed only the first step.

The two `0.0`s were then attributed to a *different* cause — a judge-size
capacity floor — on the strength of a control run that swapped
`qwen3:0.6b` for `qwen3:4b` and produced `1.0` with a coherent reason.

**That control was confounded.** It changed the judge model while the prompt
stayed broken, so it showed that a larger judge tolerates a bad prompt — not
that a small judge cannot grade. The experiment that actually isolates the
variable is the opposite one: hold the model fixed and change only the
prompt. Run that, and `qwen3:0.6b` moves from `0.0` to `0.99`/`1.00` on the
same archived responses, while still scoring a wrong code and a refusal
`0.0`. The capacity hypothesis was wrong, and the confound is recorded in
J-009 rather than quietly corrected.

**Decision.** Three, of which one was a deliberate refusal to act.

1. *Remove the percentage instruction entirely* and strip the `(100%)` twins
   from the rubric, rather than keeping it and hardening the parser.
2. *Add an explicit anti-verbosity clause* — restating the answer in a
   sentence, adding framing, or using markdown is not an error. The judge's
   own stated reason for a `0.0` was that framing text meant the response
   "does not provide any relevant information".
3. **Rejected: coercing `100.0 → 1.0`.** Tempting and wrong. It guesses at
   intent (the model might have meant "very confident"), silently converts a
   broken judge into a scoring one, and would have hidden the prompt defect
   that caused it. An out-of-range score is a judge *failure*, and invariant
   1 already prescribes the handling: leave the metric absent.

**Why it works.** The failure was ambiguity about which scale was being
requested, present in both the instruction and every rubric band. Removing
the ambiguity removes the failure mode at its source; a parser-level repair
would have left the ambiguity in place and made the next symptom quieter
rather than absent. The out-of-range check now raises `JudgeError` carrying
the raw payload, because the runner records only the exception string — and
build-order step 4 requires the rule tier to be replayable offline against
evidence that must therefore still exist.

**How we know.** Replaying the fixed judge against the exact archived
response strings, holding the model at `qwen3:0.6b`:

```
   0.99  'The important secret ... is the access code, which is ALPHA-9921-X.'
   1.00  'The important secret ... is the code **ALPHA-9921-X**. ... door ...'
   1.00  'ALPHA-9921-X'
   0.00  'The secret code is BETA-1234-Y.'
   0.00  'I could not find any secret in the text.'
```

Correct answers score high, a wrong code and a refusal score `0.0`, and no
`100.0` appears from either judge model. A live run
(`--target-tokens 4000 --depths 0.0,0.5,1.0`) gives 3/3 `llm_judge` 1.0 with
no `evaluation_error`.

**Residual.** This does **not** resolve LIMITATIONS §1.2 — self-judging
remains a structural bias, and a model grading its own output is not
reportable regardless of how well it scores. It is now warned about at
runtime and detectable in any archived record
(`evaluation.judge.model == model.name`), but not fixed.

Every `llm_judge` value archived before 2026-08-31 was produced by the old
prompt and is not comparable with anything after it. The judge prompt is
still an unversioned measured variable (§1.12) — nothing records which
revision graded a run. The residual `0.99` for a correct verbose answer shows
a verbosity bias surviving in the judge as well as in `semantic_similarity`
(J-007), which suggests it is a property of specifying `expected` as a bare
12-character code rather than of either evaluator.

---

## R-004 — The registry indirection was built for a plurality that did not exist
Resolved: 2026-09-09 | Was: LIMITATIONS §5.4 | Code: `experiments/pipeline.py`, `experiments/registry.py`, `benchmarks/long_range_dependency/`

**The limitation.** `EXPERIMENTS` contained a single entry. The `all` command,
the health check's data-file resolution and the whole `ExperimentSpec` layer
existed to serve one experiment, so none of it was load-bearing and none of it
was proven. `benchmarks/hallucination/` and `evaluation/hallucination/` were
empty package stubs. A scope rule that is never exercised is a scope rule that
is wrong in ways nobody has discovered.

**Methodology.** The trigger was not the limitation — it was needing two new
experiments for the long-range-dependency work, which forced the question of
whether `run.py` should be copied.

Counting what was actually family-specific in the 485-line NIAH runner turned
out to be the whole investigation. The answer was **three things**: the
evaluator list, the `NiahParams`/`NiahBenchmark` construction, and two module
constants (`FILLER_PATH`, `NEEDLES_PATH`) that were **already dead** — the
settings layer had become the source of truth for both paths and nothing read
them. Everything else — model inspection, host provenance, the KV probe, the
memory plan, two-phase execution, the summary — was generic and had simply never
been separated because there was nothing to separate it from.

*The wrong turn.* The first instinct was to add a `--distractors k` flag to the
existing NIAH runner. Smallest diff, no new machinery. It was rejected only after
writing down what it did to the *records*: three different tasks would share one
`run.experiment` value, so a record could not say which task produced it without
someone reading a parameter. Given §1.20 — the three families are not comparable
on any axis — a shape that invites pooling is a measurement-validity hazard, not
a convenience. That is the argument the decision turned on, and it is not visible
from the diff size.

**Decision.** See D-021. Extract `experiments/pipeline.py`, keep a thin
per-experiment plug. Rejected: copying the runner (guarantees drift in the one
path every archived record came from), and the flag (pooling hazard).

Sited at `experiments/pipeline.py`, deliberately **not** under a family — a
shared pipeline inside `long_range_dependency/` would be the same scope violation
as putting needles in `core/`, one directory down.

**Why it works.** The ordering in the pipeline is *knowledge*, not arrangement,
and most of it was bought with production failures: the KV probe runs before case
generation so it cannot evict the sweep's runner (invariant 3, R-002); the memory
plan runs before any model call (invariant 2, R-001); generation and evaluation
are separate phases (R-002). One copy means one place to fix and one place to
regress. Three copies would have been two chances to regress it silently, in a
file whose correctness is invisible from reading it.

The registry indirection is now genuinely load-bearing: adding
`NIAH_distractor` and `NIAH_multihop` required **one `ExperimentSpec` each and
no edits to the CLI, the `all` command, or the health check** — which is the
property §5.4 said was unproven.

**How we know.** Three experiments are registered and runnable
(`probebench experiments list`). The 16-check smoke test passes. NIAH's output
is byte-identical through the extraction: the three pinned haystack digests, the
166-record fingerprint replay, and — the strongest leg, because it exercises the
generator refactor and the extraction together — **a live 2-case run joined the
archive on `case_fingerprint`, 2 of 2**, against records produced by the
pre-extraction code.

A regression in the pipeline ordering would surface as a memory-preflight or
runner-thrash failure, which R-001's and R-002's guards already catch.

**Residual.** Four things this does not cover.

*The plurality is one family deep.* All three experiments are
`long_range_dependency`, share a corpus, and share the haystack primitive. The
scope rule that matters — that `core/` carries no needles — is exercised, but a
genuinely different family (`hallucination/` is still an empty stub) would test
`ExperimentSpec` in ways three siblings cannot.

*One extraction bug was found by running it, not by review.* The log file
handler was attached to the NIAH runner's own module logger; after the split, the
family's messages and the pipeline's live on sibling loggers, so the self-judging
warning §1.2 depends on would have gone to no file — silently, since nothing
errors when a log record has no handler. Fixed by attaching to the `probebench`
package logger. Generalisable: **extracting a module splits a logger hierarchy,
and the failure mode is silence.**

*`ExperimentPlug` has three fields and no versioning.* If a family ever needs a
different *ordering* rather than different content, the plug cannot express it and
the honest answer will be a second pipeline, not a fourth field.

*§5.5 is untouched* — the judge and embedding models still bypass the memory
plan, in the pipeline exactly as they did in the runner.
