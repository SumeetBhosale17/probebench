# ProbeBench — Research Journal

A running record of what was observed, what it meant, and when we knew it.

Companion documents: [DESIGN.md](DESIGN.md) (mechanism),
[LIMITATIONS.md](LIMITATIONS.md) (threats to validity),
[DECISIONS.md](DECISIONS.md) (what we chose in response, and against what).

---

## Why this file exists

The most valuable result in this project so far was not planned. The memory
work started as a crash — a 36 GB KV cache allocation on a 14 GB machine —
became a root-cause analysis, then a predictive model validated against the
observed failure, then a CLI command, and it is arguably the most novel thing
in the repo. Nothing about that sequence was on a roadmap.

DESIGN.md records the *conclusion* of that work. It does not record that the
formula was derived by checking a raw allocation figure against
`2 · 36 · 8 · 128 · 2 · 256000` and finding an exact match, which is the part
a paper's methods section actually needs. This file records the process.

## How to use it

**Append-only, newest last.** One file. No tooling, no template to fetch.

### Entry format

An ID, a date, a title, a status line, and six lines:

```markdown
## J-007 — 2026-08-29 — Judge scores saturate at 1.0 on every case
Status: open

**Observed.**    What actually happened. Paste raw output.
**Expected.**    What you thought would happen.
**Mechanism.**   Why. "unknown — hypotheses: …" is a valid entry.
**Validated.**   The command, file, or arithmetic that confirms it. Or "not yet".
**Implies.**     What changes because of this.
**Disposition.** publishable | limitation | note
```

### The trigger rule: write the entry BEFORE the fix

Open this file first when any of these happen:

- an unexpected crash or traceback
- a number that is anomalous, saturated, or will not move
- a discrepancy between advertised and measured behaviour
- a fix that works but you cannot explain

Paste the raw error and the exact command that produced it, *then* fix.

**The fix usually destroys the evidence.** The KV formula was only derivable
because `attempted to allocate 36000.00 MB` survived long enough to be
checked against the arithmetic. Had the context size been lowered first, that
number would be gone and the predictive model with it.

### Graduation

| Entry is… | Graduates to | Keeps |
|---|---|---|
| an explanation of a mechanism | DESIGN.md — what/how/why | its ID + a `graduated →` marker |
| a threat to a claim | LIMITATIONS.md — with severity and removal condition | same |
| a result | paper material | same |
| neither | stays here as a note | — |

**Entries are never deleted or rewritten.** They record what we believed at
the time, which is the part that makes this worth keeping. Correct an entry
by appending a new one that references it.

### Keep it cheap

Incomplete entries are committable. `Mechanism: unknown` is a valid entry —
recording the observation is the point; explaining it is a later job. A
process too expensive to follow does not get followed.

---

# Entries

## J-001 — 2025-08-19 — KV cache allocation of 36 GB on a 14 GB machine
Status: graduated → DESIGN §2.1, §3.1; LIMITATIONS §2.1

**Observed.** `qwen3:4b` at a requested context of 256,000 tokens killed the
Ollama runner outright:

```
ollama._types.ResponseError: llama-server process has terminated: exit status 1:
ggml_aligned_malloc: insufficient memory (attempted to allocate 36000.00 MB)
alloc_tensor_range: failed to allocate CPU buffer of size 37748736000
llama_init_from_model: failed to initialize the context:
    failed to allocate buffer for kv cache (status code: 500)
```

Host: 23 GiB RAM (≈14 GiB free), RTX 3050 Laptop 4 GiB VRAM, **zero swap**.

**Expected.** The run to proceed. The existing guard in `run.py` compared the
requested window against `model_info.context_length` — 256,000 < 262,144 — so
it passed.

**Mechanism.** The KV cache holds a key and a value vector per layer per
token and scales linearly with context:

```
kv_bytes_per_token = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element
```

For `qwen3:4b` (36 layers, 8 KV heads via GQA, head_dim 128, f16):
`2 × 36 × 8 × 128 × 2 = 147,456` bytes/token, and
`147,456 × 256,000 = 37,748,736,000` bytes = 36,000 MiB.

The gap was conceptual, not a bug: *"the architecture supports this context"*
and *"this machine can afford this context"* are different questions, and
only the first was being asked.

**Validated.** The prediction matches the reported allocation **exactly** —
36,000 MB predicted, `attempted to allocate 36000.00 MB` observed. Later
re-checked through the CLI: `probebench plan qwen3:4b` reports 35.2 GiB at
256,512 ctx, and `--target-tokens 256000 --dry-run` now exits 1 with
"Insufficient memory" before any model is loaded.

**Implies.** Memory feasibility is a first-class experimental constraint, not
an operational detail. A model's advertised context window is not the context
window that can be benchmarked on a given host — `qwen3:4b` advertises
262,144 tokens; the reference machine tops out near 88,800. Any long-context
claim must state the host's memory budget, because it bounds what was
measurable at all.

**Disposition.** publishable. This is the template case for the whole
journal: crash → root cause → predictive model → validation against the
original observation → CLI command. None of it was planned.

---

## J-002 — 2025-08-19 — HTTP 404 for a model that had already answered
Status: graduated → DESIGN §2.2, §3.2, §3.3; LIMITATIONS §4.6 (root cause still open)

**Observed.** On a shared lab machine (`pc-13@ProjectLab-13`, RTX 3050 6 GB,
models `llama3.1:8b` and `qwen3:8b`), a 20-case run completed cases 1 and 2
normally and then failed at case 3:

```
ollama._types.ResponseError: model 'qwen3:8b' not found (status code: 404)
```

The failure landed inside the **judge** call, not generation. A second run
with `generation=llama3.1:8b, judge=qwen3:8b` failed the same way. Two
completed cases were lost with it.

**Expected.** The run to complete, or at worst to fail on a model that was
never present — not on one that had just answered twice.

**Mechanism.** Two parts, and only the first is confirmed.

*Confirmed — runner thrash.* Ollama keys a `llama-server` runner on
`(model, num_ctx, …)`. Generation passed a per-case `num_ctx`; the judge
passed `options={"temperature": 0}` with **no `num_ctx`**. Those are two
different runners. With `qwen3:8b` at Q4 (~5.2 GB) on a 6 GB card they cannot
coexist, so every case did `load gen → generate → EVICT → load judge → judge
→ EVICT`. That is ≈5 GB of churn twice per case, 40 times over the run.

*Unconfirmed — the 404 itself.* Thrash explains the pressure but not a 404,
which means "name not resolvable in the manifest store". A model that
answered three requests cannot have ceased to exist, so the server's view of
its model store must have changed mid-run. Leading hypothesis: the
shared-machine trap — a user-launched `ollama serve` and a systemd `ollama`
service use different model directories and both bind `:11434`. If the
foreground server is OOM-killed during a 5 GB reload and the service takes
the port, every later request hits a different, possibly empty, store.

**Validated.** The thrash mechanism was validated by fixing it and measuring:
two-phase execution on `qwen3:4b`, 2 cases at 4k, gave evaluation times of
5.7 s for case 1 (judge cold-loading) and **1.7 s** for case 2 (judge runner
resident). The store hypothesis was **never confirmed on that host** — the
diagnostics were not run there.

**Implies.** Three separate engineering responses, each addressing a
different layer: remove the thrash (two-phase execution), remove its cause
(pin the judge's `num_ctx`), and stop one bad case from destroying good ones
(failure isolation with `status`/`error`). Also: serving-layer artefacts
contaminate timing measurements — latency from a single-phase harness on a
memory-constrained host measures model loading, not inference, and any
reported latency must state which mode produced it.

**Disposition.** publishable (the thrash mechanism and the two-phase
measurement); limitation (LIMITATIONS §4.6 — the root cause of the 404
remains unconfirmed). An honest example of an entry that graduates only
partly and stays open on the rest.

---

## J-003 — 2026-08-29 — Every metric in every successful run is 1.0
Status: open

**Observed.** Across all four archived result files — 34 records, `qwen3:4b`,
targets 4,000, depths 0.00–1.00, all six needles — every case scored 1.0 on
every metric:

```
$ jq -r '.metrics | tostring' results/raw/*.jsonl | sort | uniq -c
      9 {"lexical":1.0,"semantic_similarity":0.9999999999999998,"llm_judge":1.0}
     15 {"lexical":1.0,"semantic_similarity":1.0,"llm_judge":1.0}
      5 {"lexical_exact_match":1.0,"semantic_similarity":0.9999999999999998,"llm_judge":1.0}
      5 {"lexical_exact_match":1.0,"semantic_similarity":1.0,"llm_judge":1.0}
```

The only variation anywhere is floating-point noise in `semantic_similarity`
— the split into four rows is the metric-key rename of J-005, not a
difference in outcome. Zero failures have ever been observed.

**Expected.** Some degradation with depth, or at least *some* spread to
distinguish cells of the grid. NIAH is supposed to be a difficulty curve.

**Mechanism.** Partly understood. The cases are far too easy: 4,000-token
haystacks against a model advertising 262,144, with a single unambiguous
needle marked `[IMPORTANT SECRET]` and a system prompt instructing exact
extraction. Nothing here is near the model's limit. `semantic_similarity` is
separately saturated by construction — cosine similarity between embeddings
of two short codes is near-1 regardless of correctness (LIMITATIONS §1.5).
What is *not* yet known is where the curve actually breaks: no run has gone
past 4,000 tokens.

**Validated.** Not yet — no failing run exists to validate against. That is
precisely the finding.

**Implies.** This is the observation motivating the whole diagnostic pivot.
Two consequences:

1. The benchmark currently has **no discriminating power**. A 1.0 on every
   cell is not a result about the model; it is a statement that the task is
   too easy to measure anything.
2. **A taxonomy of failure modes cannot be validated against a dataset with
   no failures.** Classifier precision and recall are undefined, label
   reachability is unknown, and a rule that never fires is indistinguishable
   from a rule that is correct. Worse, `niah.distractor_retrieval` is
   unreachable *by construction* — `create_haystack` inserts exactly one
   needle, so "wrong needle retrieved" cannot happen.

Sequencing follows directly: produce failures first, derive the taxonomy from
what they actually look like, then build the classifier. Longer contexts
toward the ≈88k feasibility ceiling, a finer depth grid, a weaker model, and
distractor needles — noting that the last of those **changes what is being
measured**, turning NIAH from retrieval into discrimination.

**Disposition.** publishable, eventually — "the standard NIAH setup is
saturated at the sizes a commodity host can run" is a real methods finding,
and the failure inventory that comes out of fixing it is the paper's data.
For now: open, and the top-priority issue in CLAUDE.md.

---

## J-004 — 2026-08-29 — `case_id` is not stable across runs
Status: open

**Observed.** The same case — same target size, same depth, same needle,
therefore byte-identical prompt — carries different `case_id`s in two
archived runs:

```
$ jq -r 'select(.case.depth==0.25 and .case.target_tokens==4000)
         | "\(.case.case_id)  \(.case.needle[0:40])"' results/raw/*.jsonl

# run 55a05b84 (--needles 5):
niah_4000_0.25_0006  The secret access code is ALPHA-9921-X.
# run 6c868540 (--needles 2):
niah_4000_0.25_0003  The secret access code is ALPHA-9921-X.
```

**Expected.** A case identifier to identify a case.

**Mechanism.** `_build_case_id` returns
`f"niah_{target_tokens}_{depth:.2f}_{case_number:04d}"`, where `case_number`
is a counter incremented across the *entire* sweep
(`benchmarks/long_range_dependency/NIAH/benchmark.py`). It therefore depends
on the sweep's composition — how many needles, how many depths, which cells
were skipped by the `--context` ceiling — rather than on the case's own
content. The needle, which determines the expected answer, does not appear in
the id at all.

Collisions are constructible, not merely theoretical: `--depths 0,0.25
--needles 1` and `--depths 0.25 --needles 2` both emit
`niah_4000_0.25_0002`, with **different needles and different expected
answers**.

**Validated.** The instability is confirmed against the archive (command
above). The collision is derived from the generation loop and has not been
run; it follows directly from the counter's ordering and needs no experiment,
but flagging it as derived rather than observed.

**Implies.** "Do different models fail on the same inputs?" cannot currently
be answered, because there is no sound key to join on. Any cross-model
analysis written against `case_id` today would silently compare unlike cases.

The fix is content-addressed identity: a sweep-independent `case_key` (the
grid coordinate) plus a `case_fingerprint` hashing everything that determines
the model's input. Note the interaction with LIMITATIONS §1.1 — building
haystacks with cl100k for every model is what currently makes cases
byte-identical across models, so fixing §1.1 will break fingerprint joins by
design. That argues for landing identity *first*, while a clean baseline
still exists to measure the §1.1 fix against.

**Disposition.** limitation — candidate to graduate into LIMITATIONS §1 as a
threat to every cross-model claim, once the severity is settled.

---

## J-005 — 2026-08-29 — Three record shapes all declare `schema_version: "1.0"`
Status: open

**Observed.** Every archived record claims the same schema version:

```
$ jq -r '.schema_version' results/raw/*.jsonl | sort | uniq -c
     34 1.0
```

But they are not the same shape. At least three variants exist:

| | `model` | metric key | `response.status` | `generation.num_ctx` |
|---|---|---|---|---|
| oldest 3 files | bare string `"qwen3:4b"` | `lexical` | absent | absent |
| `f163218e` | nested dict | `lexical_exact_match` | absent | absent |
| current code | nested dict | `lexical_exact_match` | present | present |

**Expected.** LIMITATIONS §5.2 records one undeclared change (`status` /
`error` added without a version bump). Reading the archive, there are at
least three.

**Mechanism.** Invariant 7 — bump `CURRENT_SCHEMA_VERSION` when
`to_record()` changes — was violated repeatedly rather than once. The
supporting machinery exists and is unused: `core/migrations.py` has an empty
`MIGRATIONS` map, and `SUPPORTED_SCHEMA_VERSIONS` contains only `"1.0"`.
Nothing reads result files back, so nothing ever failed loudly enough to
notice. The rename `lexical` → `lexical_exact_match` is the worst of the
three: it silently changes the *keyspace of the metrics dict*, so an
aggregation across the archive would drop a third of the data rather than
error.

**Validated.** Confirmed by inspection of all four files (commands above).

**Implies.** Two things. First, LIMITATIONS §5.2 understates the problem and
should be widened — a migration written against the §5.2 description alone
would fail on three of the four archived files. Second, migrations must
detect shape by **field presence**, not by declared version, because the
declared version carries no information here.

It also explains *why* the invariant was violable: a schema contract with no
reader is unenforced. The first consumer of the migration path — a
`reporting/load.py` that reads JSONL and normalises it — is what will make
invariant 7 self-enforcing, and is a reason to build it before more runs are
archived.

**Disposition.** limitation — should graduate by widening LIMITATIONS §5.2
from "the version was not bumped" to "three shapes share one version, and
the metric keyspace changed silently".

---

## J-006 — 2026-08-29 — The judge returned `100.0`, and graded two correct answers `0.0`
Status: open — mechanism partly corrected by J-009

**Observed.** Run `0ca55bd787be`, `qwen3:0.6b` generating and `qwen3:0.6b`
judging, three cases at 32k tokens, depths 0.00 / 0.50 / 1.00. One case
crashed the judge:

```
2026-08-29 17:40:56,622 ERROR probebench.core.runner: Evaluator llm_judge failed for case niah_32000_0.50_0002
Traceback (most recent call last):
  File "src/probebench/core/runner.py", line 108, in evaluate
    evaluation = evaluator.evaluate(
  File "src/probebench/evaluation/long_range_dependency/NIAH/judge/judge.py", line 136, in evaluate
    score=validate_score(score),
  File "src/probebench/core/evaluator.py", line 40, in validate_score
    raise ValueError(f"Evaluation score must be in [{minimum}, {maximum}], got {score}.")
ValueError: Evaluation score must be in [0.0, 1.0], got 100.0.
```

All three responses contain `ALPHA-9921-X` verbatim — 3/3 correct
retrievals. The metrics:

| case | depth | predicted | lexical | semantic | judge |
|---|---|---|---|---|---|
| 0001 | 0.00 | `The important secret ... is the access code, which is ALPHA-9921-X.` | 1.0 | 0.732 | 0.0 |
| 0002 | 0.50 | `ALPHA-9921-X` | 1.0 | 1.0 | *absent* (raised on 100.0) |
| 0003 | 1.00 | `The important secret ... is the code **ALPHA-9921-X**. ...` | 1.0 | 0.649 | 0.0 |

The two recorded judge reasons are self-refuting:

> "The model response incorrectly states the expected answer as 'ALPHA-9921-X'
> but does not correctly identify the 'important secret' mentioned in the text."

> "The model response incorrectly states that the code is 'ALPHA-9921-X' but
> does not provide any relevant information about the text's content. The
> expected answer is missing, and the response is incomplete."

Both name the expected answer in the clause that calls the answer missing.

**Expected.** Three judge scores of 1.0. The task is exact-string extraction
and the exact string is present in every response.

**Mechanism.** Two independent faults that happen to share one column.

*The `100.0`* is a unit error invited by the prompt. `JUDGE_SYSTEM_PROMPT`
asks the model to "score the response as a percentage from 0 to 100 ... then
report that percentage divided by 100", and then restates every rubric band
in both units (`1.0 (100%)`, `0.0 (0%)`). That is a two-step transform on a
751M-parameter model running with `think=False`. It performed step one and
skipped step two. `format="json"` guarantees the output parses; it constrains
no value range. Note that `100.0` is the *correct grade* for case 0002 — the
prediction was the bare expected string — so the only case the judge graded
correctly is the one that hard-failed.

*The two `0.0`s* are a capacity failure, not a prompt failure. This is
LIMITATIONS §1.2 (self-judging) meeting a floor: `qwen3:0.6b` cannot reliably
run compare-and-decide, and `think=False` removes the reasoning it would need
to. The `llm_judge` column here measures the judge, not the model under test.

**Validated.** Directly, by a control run. `b9fc2be30af6` is the same
generation model (`qwen3:0.6b`) at 32k / depth 1.00 with `--judge-model
qwen3:4b`:

```
predicted: "The important secret mentioned in the text is ALPHA-9921-X."
metrics:   lexical_exact_match 1.0, semantic_similarity 0.795, llm_judge 1.0
reason:    "The model response exactly matches the expected answer with no
            additional or incorrect information."
```

Same generation model, same needle, same depth, same prompt — swapping only
the judge moves `llm_judge` from 0.0 to 1.0 and produces a coherent reason.
The judge column was a property of the judge. The semantic column did not
move (see J-007), which separates the two faults cleanly.

**Implies.** Four things.

1. The prompt's percentage detour has no benefit and one failure mode.
   Ask for `0.0`–`1.0` directly.
2. Do **not** coerce `100.0 → 1.0`. The coercion is a guess about intent, and
   it would mask exactly this class of prompt regression. `validate_score`
   raising, and invariant 1 leaving the metric absent, is the system working.
3. The raw judge payload is discarded — only the exception string survives —
   so the `reason` accompanying the `100.0` is unrecoverable. Build-order
   step 4 requires the rule tier to be replayable over stored JSONL; a record
   that keeps the error but drops the evidence cannot support that.
4. Self-judging needs to be visible at analysis time, not just documented in
   LIMITATIONS. A run where judge == generation model should say so loudly
   and carry a filterable marker in the record.

**Disposition.** limitation — graduates into LIMITATIONS §1.2, which should
be widened from "the judge defaults to the generation model" to "a small
self-judge produces confidently inverted grades, and a failure corpus graded
this way has poisoned ground truth before hand-labelling starts."

---

## J-007 — 2026-08-29 — `semantic_similarity` ranks a correct verbose answer below a correct terse one
Status: open

**Observed.** Across four correct retrievals of `ALPHA-9921-X` in runs
`0ca55bd787be` and `b9fc2be30af6`, `semantic_similarity` spans 0.649 to 1.0:

| predicted | semantic |
|---|---|
| `ALPHA-9921-X` | 1.000 |
| `The important secret mentioned in the text is ALPHA-9921-X.` | 0.795 |
| `The important secret ... is the access code, which is ALPHA-9921-X.` | 0.732 |
| `The important secret ... is the code **ALPHA-9921-X**. This code is tied to unlocking the door ...` | 0.649 |

Every one of these is a fully correct answer. `lexical_exact_match` is 1.0
for all four. The score is monotonically decreasing in response length.

**Expected.** Four roughly equal scores, since the task was performed
correctly four times.

**Mechanism.** `EmbeddingSemanticEvaluator` embeds the *entire* response and
cosine-compares it against `case.expected`, which is the bare code string
`ALPHA-9921-X`. Every additional word of framing moves the response embedding
away from a 12-character code. So the metric ranks brevity, not correctness.
The class docstring already says "this is a similarity metric, not a
correctness metric" — the code is honest; the presentation is not. The CLI
summary table prints it in the same row as `lexical_exact_match` and
`llm_judge` under a `context` axis, which reads as three measurements of
correctness against context length.

**Validated.** Table above; four responses, one metric, no failures among
them. The control run in J-006 confirms the fault is independent of the
judge: swapping the judge model moved `llm_judge` and left
`semantic_similarity` at the same verbosity-driven value.

**Implies.** Any context-length curve drawn on this column is plotting
response style, not retrieval. That is a live threat: NIAH degradation is
expected to show up as longer, hedgier answers at depth, which this metric
would render as a falling curve *even if every answer stayed correct* —
producing a publication-shaped result with no content.

Fixing it changes what is measured, so it is a decision and not a patch. The
options are to drop the metric from NIAH, to redefine it as a max over
response sentences (measuring "does any part of this response mean the
expected answer"), or to keep it and rename it so no one reads it as
correctness. Whichever is chosen, the metric *semantics* change and the
existing archive is not comparable across the change.

**Disposition.** limitation — new LIMITATIONS entry under §1, removal
condition: the metric is either dropped, redefined with a version marker, or
renamed to state what it measures.

---

## J-008 — 2026-08-29 — Correct retrieval with a confabulated justification, and no label for it
Status: open

**Observed.** Run `0ca55bd787be`, case `niah_32000_1.00_0003`:

```
needle:    "The secret access code is ALPHA-9921-X."
predicted: "The important secret mentioned in the text is the code
            **ALPHA-9921-X**. This code is tied to unlocking the door, as
            indicated in the passage where the doctor's bow is described."
```

The needle sentence contains no door, no doctor and no bow. The model
retrieved the code correctly and then invented a provenance for it.

**Expected.** Either the code alone, or the code with a justification drawn
from the needle sentence.

**Mechanism.** The filler corpus is *War and Peace*
(`data/long_range_dependency/NIAH/filler_text.txt`), which supplies the
vocabulary:

```
$ grep -o -i "door[a-z]*" data/long_range_dependency/NIAH/filler_text.txt | sort | uniq -c
    333 door
      4 doorpost
     26 doors
     13 doorway
      2 doorways
$ grep -o -i "bow[a-z]*" data/long_range_dependency/NIAH/filler_text.txt | sort | uniq -c
     53 bow
     58 bowed
     ...
```

Ambient haystack tokens were welded into a justification for a correctly
retrieved value. This is retrieval succeeding and grounding failing, in one
response.

**Validated.** Greps above; the needle text is in the record itself.

**Implies.** The planned core taxonomy has no label for this. It is not
`WRONG_ANSWER` — the answer is right. It is not `FORMAT_VIOLATION`,
`NON_ANSWER` or `INSTRUCTION_IGNORED`. Under the current label set a rule
classifier would decide `OK`, because the expected string is present, and
the confabulation would be invisible in the record.

This matters for build order. Step 3 says to freeze the taxonomy *from the
observed inventory* rather than implement the hypothesis in CLAUDE.md, and
this is the first entry in that inventory: a correct-answer-with-fabricated-
grounding mode that the hypothesis does not contain. It is also precisely
what three floats cannot express — `lexical_exact_match` 1.0,
`llm_judge` 0.0 for the wrong reason, `semantic_similarity` 0.649 for the
wrong reason — which is the argument for the pivot, stated in one case.

Note also that J-003 ("every metric in every successful run is 1.0") still
stands: this run contains zero *retrieval* failures. The sub-1.0 values here
are evaluator artefacts (J-006, J-007), not model failures. The failure
corpus does not exist yet.

**Disposition.** publishable — taxonomy inventory. Candidate core label
`UNGROUNDED_JUSTIFICATION`, or a NIAH subtype under a new core parent, to be
decided at freeze time and not before more instances are observed.

---

## J-009 — 2026-08-31 — The judge's inverted grades were prompt-induced, not a capacity floor
Status: open — corrects J-006's stated mechanism

**Observed.** After removing the percentage detour from `JUDGE_SYSTEM_PROMPT`
and adding an explicit "do not penalise a correct answer for being verbose"
clause, the **same** `qwen3:0.6b` judge was replayed against the exact
responses it had graded `0.0` in run `0ca55bd787be`:

```
=== qwen3:0.6b
   0.99  'The important secret mentioned in the text is the access code, which is ALPHA-9921-X.'
   1.00  'The important secret ... is the code **ALPHA-9921-X**. This code is tied to unlocking the door ...'
   1.00  'ALPHA-9921-X'
   0.00  'The secret code is BETA-1234-Y.'
   0.00  'I could not find any secret in the text.'
=== qwen3:4b
   1.00  'The important secret mentioned in the text is the access code, which is ALPHA-9921-X.'
   1.00  'The important secret ... is the code **ALPHA-9921-X**. This code is tied to unlocking the door ...'
   1.00  'ALPHA-9921-X'
   0.00  'The secret code is BETA-1234-Y.'
   0.00  'I could not find any secret in the text.'
```

Two negative probes were added that had no counterpart in the original run: a
wrong code (`BETA-1234-Y`) and a refusal. Both judges score both `0.0`.

**Expected.** Based on J-006, `qwen3:0.6b` should have kept grading the
verbose correct answers near `0.0` — J-006 attributed those to a capacity
floor and said swapping the judge model was the fix.

**Mechanism.** **J-006's mechanism was wrong in its second half.** It
separated the `100.0` (prompt fault) from the two `0.0`s (claimed capacity
fault) and cited the `qwen3:4b` control run as proof of the split. The
control was confounded: it changed the judge model, but it ran *after* no
prompt change at all — so it demonstrated that a bigger judge tolerates a bad
prompt, not that a small judge cannot grade. Holding the model fixed and
changing only the prompt, which is the experiment J-006 never ran, moves
`qwen3:0.6b` from `0.0` to `0.99`/`1.00` on the same inputs.

The likely mechanism for the original `0.0`s is the same one that produced
the `100.0`: the old prompt's percentage detour asked for a unit conversion
mid-judgement, and a 0.6b model with `think=False` spent its budget on that
rather than the comparison. The rubric's `1.0 (100%)` / `0.0 (0%)` twins
made every band ambiguous about which scale was being requested.

**Validated.** The replay above — `OllamaJudge.evaluate` called directly
against the archived response strings, both judge models, one prompt version.
The `100.0` did not reappear from either model.

Also validated live: `uv run probebench qwen3:0.6b --target-tokens 4000
--depths 0.0,0.5,1.0` gives 3/3 `llm_judge` 1.0, self-judged, no
`evaluation_error`.

**Implies.** Three corrections.

1. LIMITATIONS §1.2's conclusion "`qwen3:0.6b` is below that floor and must
   not be used as a judge" is not supported. The floor, if it exists, has not
   been located — it was never separated from the prompt fault. §1.2's real
   claim is narrower: self-judging remains a structural bias and a
   *reportable-results* problem regardless of judge size.
2. Judge-prompt quality dominated judge-model size on this task. That is a
   cheaper lever than a bigger judge, and it matters directly for
   build-order step 5, which extends this same prompt with a `label` field —
   the label contract needs the same scrutiny the score contract just got.
3. `0.99` for a correct verbose answer from the 0.6b judge means a residual
   verbosity penalty survives in the judge as well as in
   `semantic_similarity` (J-007). It is negligible at this magnitude, but it
   is the same bias appearing in two independent evaluators, which suggests
   it is a property of how `expected` is specified — a bare 12-character
   code — rather than of either evaluator.

None of this restores confidence in the archived `llm_judge` column: those
runs used the old prompt and remain invalid. It changes *why* they are
invalid.

**Disposition.** limitation — corrects LIMITATIONS §1.2, and adds a note that
the judge prompt is a measured variable, not a fixed constant.

---

## J-010 — Groundedness fires on 1 of 44 archived records, and has a judge-size floor
Status: open

**Observed.** A scratch groundedness judge — the needle supplied as the only
supporting source, asking `correct` and `grounded` as two independent fields
— was run over every record in `results/raw/` (44 records, 8 files, both
generation models). Judge: `qwen3:4b`.

```
correct=1.0 grounded=true   43
correct=1.0 grounded=false   1
```

The single positive is the J-008 case, with the invented claim quoted back
verbatim:

```
case:      niah_32000_1.00_0003  (0ca55bd787be)
needle:    The secret access code is ALPHA-9921-X.
predicted: The important secret mentioned in the text is the code
           **ALPHA-9921-X**. This code is tied to unlocking the door, as
           indicated in the passage where the doctor's bow is described.
correct:   1.0
grounded:  false
claim:     "This code is tied to unlocking the door, as indicated in the
            passage where the doctor's bow is described."
```

Zero false positives on the other 43 — including the three verbose-but-clean
answers that `semantic_similarity` scored 0.649–0.795 and the old judge
scored 0.0.

On a probe set of seven hand-written responses, `qwen3:4b` scored 7/7 on both
fields, including the two cases nothing else separated: a clean-but-long
answer with ten novel hedging words (grounded), and a correct code with an
invented provenance — "issued to General Kutuzov in 1805" (ungrounded, claim
quoted). **`qwen3:0.6b` scored 1/7**: it marked every response ungrounded
except the bare code string.

**Expected.** A handful of positives across 44 records, and rough parity
between judge sizes as in J-009.

**Mechanism.** Two separate findings.

*The low base rate is J-003, not a defect of the instrument.* 41 of the 44
predictions are bare code strings — `ALPHA-9921-X`, `CRIMSON-EAGLE-44` — with
no claim in them to be ungrounded about. `grounded` is trivially true on
those and carries no information. **The archive contains only three
informative records and one positive.** A detector cannot be validated
against a corpus with nothing to detect.

*Groundedness has a judge-size floor where scoring did not.* J-009 found
`qwen3:0.6b` grades correctness fine once the prompt is unambiguous. It
cannot do groundedness at all. That is consistent with the tasks being
different in kind: scoring is a comparison against a supplied expected
answer, while groundedness requires checking each claim in the response
against a source and deciding entailment — which needs the reasoning J-009
found was not required for scoring. J-009 said the capacity floor "has not
been located"; this locates one, for a harder question.

**Validated.** Scratch scripts, read-only over `results/raw/`; the archive
was not modified. Counts above reproduce from the stored records.

**Implies.** Three things.

1. The instrument works on the one case that exists and is precise on the
   43 negatives, but **n=1 cannot establish precision**. Any claim about
   its accuracy needs failures to exist first (build-order step 2).
2. Enabling it hard-couples results to judge capacity in a way scoring does
   not. A run judged by a model below the floor will report
   `grounded: false` on nearly everything, which is worse than not asking —
   it manufactures a failure mode.
3. A refinement to J-008's stated mechanism. J-008 attributed the
   fabrication to ambient haystack tokens. `needles.txt` line 2 is *"The
   magic word to unlock the door is CRIMSON-EAGLE-44."* — but that needle
   was **not** in this case's prompt (one needle per haystack; this case's
   was ALPHA-9921-X), so it is not cross-needle leakage. "The doctor's bow"
   is clearly *War and Peace*; "unlocking the door" may instead be a generic
   prior that secret codes unlock doors — the same stereotype that produced
   needle #2. J-008's mechanism is therefore partly unconfirmed, and the two
   halves of that sentence may have different origins.

**Disposition.** note — the base rate is the reportable part, and it is an
argument for build-order step 2 rather than against the field.
