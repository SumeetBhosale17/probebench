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

---

## J-011 — 70 failures in 330: the first failure inventory, and the filler is a distractor
Status: open

**Observed.** `llama3:8b` over a 5 × 11 × 6 grid (targets 7,000–8,000; depths
0.0–1.0 in steps of 0.1; six needles), 330 cases, all `status: ok`. **70
lexical failures.** Clustered with deterministic rules over the stored JSONL,
no model calls:

| mode | n | depth signature |
|---|---|---|
| filler-content retrieval | 34 | 0.0–0.2 only |
| denied presence | 33 | bimodal: 0.0 **and** 1.0 |
| denial that still scores `lexical` 1.0 | 16 | 9 at depth 1.0 (see J-013) |
| dangling output (`"...is:"` then nothing) | 5 | middle depths only |
| fabricated code | 0 | — |
| a different planted code | 0 | — |

Corrected accuracy (excluding the J-013 false positives), rows = target
tokens, columns = depth:

```
           0.0   0.1   0.2   0.3   0.4   0.5   0.6   0.7   0.8   0.9   1.0
  7,000   0.00  0.83  1.00  1.00  0.83  0.83  0.67  1.00  0.83  0.83  0.17
  7,250   0.33  0.83  1.00  1.00  1.00  1.00  1.00  0.83  0.83  0.83  0.67
  7,500   0.00  0.67  0.67  0.83  1.00  1.00  0.83  0.67  1.00  0.83  0.33
  7,750   0.00  0.33  0.33  0.83  1.00  1.00  1.00  0.67  0.83  0.83  0.17
  8,000   0.00  1.00  0.83  0.83  0.83  1.00  0.83  0.67  1.00  0.83  0.33
    col   0.07  0.73  0.77  0.90  0.93  0.97  0.87  0.77  0.90  0.83  0.33
```

The filler-retrieval mode, verbatim:

```
d=0.0  "The important secret mentioned in the text is the appointment of Baron
        Funke as the first secretary at Vienna, which is being sought by
        others through the Dowager Empress Márya Fëdorovna."
d=0.1  "The important secret mentioned in the text is that the Dowager Empress
        wants Baron Funke to be appointed as the first secretary at Vienna."
```

**Expected.** J-003 said there were no failures anywhere in the archive. A
non-trivial failure rate was the goal of build-order step 2, and step 2 has
not been done — no distractors were injected, no generator change was made.

**Mechanism.** Two, and neither is the one build-order step 2 planned for.

*The filler corpus is not semantically neutral.* `filler_text.txt` is *War
and Peace*, which opens with court intrigue about a secret appointment being
pushed through the Dowager Empress. That is a genuine, better-formed answer
to "what is the important secret mentioned in the text?" than a floating code
string. The model is not failing to retrieve; it is retrieving a competing
answer that the corpus actually contains.

The depth signature confirms it: 32 of the 34 filler retrievals occur at
depths 0.0–0.2, and the mode disappears entirely from depth 0.3 onward. The
intrigue is at the *start* of the filler, so a needle at depth ≥0.3 arrives
after it, and recency decides.

*Accuracy is U-shaped in depth, not monotone.* 0.07 at the start, 0.97 in the
middle, 0.33 at the end — the inverse of the familiar "lost in the middle"
result. The two collapses have different causes: filler retrieval at the
start, artifact rejection at the end (J-012).

**Validated.** Rule clustering over the stored file, reproducible offline.
Corroborated independently by `85d237650c49` (`qwen3:0.6b`, 32k/36k/40k ×
5 depths, judge `qwen3:4b`), which shows the same mode in a different family
at a different scale:

```
32,000 -> 5/5 correct
36,000 -> 3/5   (fails at depth 0.00, 0.25)
40,000 -> 2/5   (fails at depth 0.00, 0.25, 0.50)

d=0.00 "...the countess's daughter's involvement in the war and the recruits"
d=0.25 "...the Rostóv's house is located in Petersburg"
d=0.50 "...the young man and the young hussar are involved in a crucial decision"
```

Same failure mode, same shallow-depth concentration, and — unlike the
`llama3:8b` sweep, whose 7,000–8,000 range is only 14% of one window — a
visible **length** effect: 5/5 → 3/5 → 2/5 across 32k → 36k → 40k.

**Implies.** Four things.

1. **`niah.distractor_retrieval` is not unreachable.** CLAUDE.md's taxonomy
   marks it "unreachable **by construction** — one needle per haystack". It
   fired 34 times. The distractor is not planted; it is *in the filler*. The
   label is reachable today, and the generator change in build-order step 2
   is not required to reach it.
2. **Step 2 is partly already done, by accident.** A failure corpus exists —
   ≥3 distinct modes, ~70 failures in one file — which is the precondition
   CLAUDE.md sets for validating a taxonomy. It arrived from a weaker model
   and a finer depth grid, not from distractor injection.
3. **LIMITATIONS §1.9 (fixed filler corpus, MINOR) is badly under-rated.**
   Needle wording alone spans 19 points of accuracy — `The secret ingredient
   is QUANTUM-LEAP-99.` scores 29/55 while `The magic word to unlock the door
   is CRIMSON-EAGLE-44.` scores 48/55 — which is a larger effect than
   anything context length does in this run.
4. The taxonomy must be frozen from *this* inventory, not from the CLAUDE.md
   hypothesis. Two hypothesised labels never fired; two observed modes have
   no label.

**Disposition.** publishable — this is the failure inventory build-order
step 3 requires, and the filler-as-distractor mechanism is a result in its
own right.

---

## J-012 — At depth 1.0 the model finds the needle and rejects it as an artifact
Status: open

**Observed.** In `2bfcd3f32b11`, depth 1.0 is the second-worst cell in the
grid (corrected accuracy 0.33). The responses are not "I could not find it" —
the model quotes the marker back and dismisses it:

```
"There is no important secret mentioned in the text. The mention of
 [IMPORTANT SECRET] is likely an error..."

"There is no important secret mentioned in the text. The mention of
 'IMPORTANT SECRET' is likely an error or a joke."

"There is no important secret mentioned in the text. The code "OMEGA-7732-Q"
 is not a real secret, but rather a fictional password for a vault that is
 randomly inserted into the text"

"There is no important secret mentioned in the text. The code "DELTA-1102-M"
 is likely a fictional or humorous identifier added by the extraction engine,
 and not a real secret or code mentioned in the text."

"There is no important secret mentioned in the text. The secret code
 "CRIMSON-EAGLE-44" is not a real secret, but rather a placeholder I inserted
 as per your instruction to only provide the secret code found in the text."
```

20 of the 30 depth-1.0 cases are this: 11 outright denials plus 9 that
mention the code while denying it (and therefore score `lexical` 1.0, J-013).

**Expected.** Depth 1.0 places the needle immediately before the question —
the shortest possible retrieval distance, and the easiest cell in the grid.
LIMITATIONS §1.10 flags the adjacency as a **MINOR** confound on the grounds
that it makes the task *too easy*.

**Mechanism.** Retrieval succeeds and is then overridden. The needle is
`\n\n[IMPORTANT SECRET]: <sentence>\n\n`, and at depth 1.0 it lands between
the last of *War and Peace* and `\n\nQuestion: ...`. In that position the
model reads the marker as part of the *prompt scaffolding* rather than the
document, notices it is incongruous with Tolstoy, and concludes it is an
error, a joke, a placeholder, or something "added by the extraction engine".
One response attributes the insertion to **itself** ("a placeholder I
inserted as per your instruction").

This is an epistemic rejection, not a retrieval failure, and the distinction
is invisible to every scalar the benchmark records: `lexical_exact_match`
scores 9 of them 1.0, and a correctness score of 0.0 on the other 11 is
indistinguishable from a model that never found the needle.

**Validated.** The responses above are the validation — the model names the
marker. Not yet separated from the alternative reading (that adjacency to the
question boundary damages retrieval in some other way), which would need a
run with the needle at depth 1.0 but followed by a paragraph of filler.

**Implies.** Three things.

1. **§1.10 has the sign wrong.** It is rated MINOR on the theory that
   adjacency makes the task too easy. Adjacency is the second-largest failure
   source in the run. The severity and the stated mechanism both need
   correcting.
2. The needle marker `[IMPORTANT SECRET]:` is a measured variable, not
   neutral scaffolding. A benchmark whose insertion format triggers rejection
   is measuring its own formatting, and the effect is confounded with depth
   because only the last position sits at the scaffolding boundary.
3. This mode has no label in the hypothesised taxonomy. It is not
   `WRONG_ANSWER` (nothing wrong is asserted), not `NON_ANSWER` (it commits,
   firmly), not `REFUSAL` in the usual sense (it is not declining, it is
   disputing the premise). Candidate: `PREMISE_REJECTED`.

**Disposition.** publishable, and a limitation — §1.10 must be corrected.

---

## J-013 — `lexical_exact_match` scores 1.0 on responses that deny the answer
Status: open

**Observed.** `LexicalEvaluator` is substring containment, so a response that
mentions the code **while denying it is real** scores a perfect 1.0:

```
lexical_exact_match = 1.0
"There is no important secret mentioned in the text. The code "DELTA-1102-M"
 is likely a fictional or humorous identifier added by the extraction engine,
 and not a real secret or code mentioned in the text."

lexical_exact_match = 1.0
"There is no important secret mentioned in the text. The text only mentions a
 fictional product called "QUANTUM-LEAP-99" as a joke or a placeholder."
```

**16 of the 330 records** in `2bfcd3f32b11` are of this shape.

```
reported lexical accuracy : 0.788   (260/330)
corrected for denials     : 0.739   (244/330)
```

The error is not uniformly distributed: 9 of the 16 sit at depth 1.0, where
they inflate the cell from 0.33 to 0.63 — nearly doubling it.

**Expected.** A metric named `exact_match` to be a lower bound on
correctness. It is not; it is an upper bound, and a loose one.

**Mechanism.** `expected in response` after casefolding. The check has no
notion of *assertion*: it cannot distinguish "the code is X" from "X is not
really a code". Any response that discusses the answer in order to reject it
satisfies containment. This is the classic failure of containment as a proxy
for extraction, and it is reachable precisely because J-012's rejection mode
produces responses that quote the needle.

Note the interaction: the bug is invisible until a model starts arguing with
the prompt. Every archived run before these two had bare-code answers, so
containment and correctness agreed and nothing exposed the gap.

**Validated.** Counted directly over the stored file with a denial regex; the
16 records are listed and each was read. The corrected grid in J-011 uses
this exclusion.

**Implies.** Three things.

1. Every accuracy number computed for `llama3:8b` before this entry is
   overstated by ~5 points, and the depth-1.0 cell by 30.
2. This is a **metric-semantics** problem, not a bug in the ordinary sense —
   fixing it changes what `lexical_exact_match` measures and breaks
   comparability with the archive. It needs a decision entry, not a patch.
3. The independent `grounded` label (D-010) caught two of these 16 in a
   60-case sample without being designed for it, which is weak evidence that
   the label tier detects a class of error the scalar tier scores as success.

**Disposition.** limitation — new LIMITATIONS entry, and it gates every
accuracy claim from these runs.

---

## J-014 — The repudiation guard flips 15, not 16, and the 16th was my error
Status: open — corrects the count in J-013 and the grid in J-011

**Observed.** The shipped `LexicalEvaluator` guard (D-011) was replayed over
the whole archive. D-011 predicted 16 records flipping 1.0 → 0.0 on
`2bfcd3f32b11`. **15 flipped.** Predictions 2 and 3 held exactly: zero
records flipped 0.0 → 1.0 in any file, and every other file was unchanged.

The record that did not flip:

```
"The important secret mentioned in the text is the secret ingredient
 "QUANTUM-LEAP-99" which is not a real ingredient but a fictional one. It
 seems to be a joke or a mistake on the part of the author, as it is not
 explained or used in the context of the story."
```

**Expected.** 16 flips, from the count in J-013.

**Mechanism.** The 16 in J-013 was measured with a **looser, ad-hoc regex**
written for analysis, which matched the bare substrings `not a real` and
`is a mistake`. The shipped guard requires `not a real (secret|code|password|
key)` and `is/as (a|an) (mistake|error|joke|...)`; this response says "not a
real **ingredient**" and "seems **to be** a joke", so neither fires.

On reading the response, **the guard is right and my count was wrong.** This
response *does* assert the expected answer — "the important secret … is the
secret ingredient QUANTUM-LEAP-99" — and then editorialises that the
ingredient is fictional. That is a correct retrieval with an unsupported
addendum, which is the `grounded` label's territory (D-010), not the lexical
metric's. The other 15 deny the answer's existence outright before or instead
of asserting it.

So the difference between the two patterns is exactly the difference between
"there is no secret, though the text mentions X" (a refusal) and "the secret
is X, though X is silly" (an answer plus commentary). The ad-hoc regex could
not tell them apart; the shipped one can.

**Validated.** Replay over all 12 archived files. Corrected figures:

```
2bfcd3f32b11 lexical: 0.788 -> 0.742   (was predicted 0.739)
depth 1.0 cell:       0.63  -> 0.33    (unchanged from J-011)
every other file:     unchanged
```

The depth-1.0 conclusion in J-011 and J-012 is unaffected — the disputed
record sits at depth 0.4.

**Implies.** Three things.

1. J-013's "16" and J-011's corrected grid should be read as 15 and the grid
   above. The overall figure is **0.742**, not 0.739. No conclusion changes;
   the U-shape, the depth-1.0 collapse and the filler-retrieval mode all
   stand.
2. A methodological point worth keeping: **the number in an analysis script
   is not the number in the shipped rule**, and quoting the first as if it
   were the second is how a heuristic acquires false authority. The
   discrepancy was only visible because D-011 wrote down a falsifiable
   prediction before the code landed.
3. An unrelated confirmation of J-005 fell out of the same replay. Three
   archived files key the metric as `metrics.lexical` and the rest as
   `metrics.lexical_exact_match`, so a naive aggregation across the archive
   silently reports 0.000 for `07d9a7cc8d6b`, `55a05b8418e9` and
   `6c868540c282` — it does not error, it under-reports. J-005 predicted
   exactly this; this is the first time it has been observed doing damage.

**Disposition.** note — the correction matters more as method than as
arithmetic.

---

## J-015 — First measured tokenizer expansion, and `done_reason` on a clean run
Status: open

**Observed.** The first records written under schema 1.2 carry the evidence
fields the runner had been discarding. On `qwen3:0.6b` at a nominal 4,000
cl100k tokens:

```
"prompt_eval_count": 4101,
"eval_count": 177,
"done_reason": "stop",
"prompt_eval_duration_ns": 581724000,
"eval_duration_ns": 1249690000,
"load_duration_ns": 2471434691,
"total_duration_ns": 4329480082
```

Cross-run joins now resolve over the whole archive. Migrating all 402
archived records to 1.2 yields 367 distinct `case_key`s, of which **13 appear
in more than one run and 6 span more than one model**:

```
niah/t32000/d0.00/n06bfb731/marked/g0  -> qwen3:0.6b, qwen3:4b
niah/t4000/d0.00/n06bfb731/marked/g0   -> 8 runs across both models
```

**Expected.** For the tokenizer: an unknown expansion, which is why §1.1 is
BLOCKING. For `done_reason`: unknown, since it had never been recorded.

**Mechanism.** Nothing surprising — this entry records the first numbers, not
a failure.

Two things worth stating precisely.

**§1.1's error is now measured rather than assumed, for one model.** 4,101
model tokens against 4,000 cl100k tokens is a **+2.5%** expansion for qwen3.
That is small, and it is the first evidence that the nominal x-axis is close
to the real one for this family. It says nothing about llama-bpe, where the
`llama3:8b` sweep ran at 7,000–8,000 against a `num_ctx` of 7,680–8,192 —
2.5% there would be ~200 tokens of headroom, and a larger expansion would
mean silent front-truncation. That measurement still cannot be made here
(llama3 is not installed on this host), which is precisely the argument for
capturing the field rather than re-deriving it.

**The `done_reason` audit is not yet possible.** O5 predicted that J-011's
five "dangling output" cases (`"The important secret ... is:"` then nothing)
would prove to be `done_reason: "length"` — instrument truncation rather than
model failure. This run is `"stop"` on both cases, but they are short correct
answers on a model that does not produce dangling output; the hypothesis is
untested until the field exists on a run that actually reproduces the mode.
`2bfcd3f32b11` cannot be re-run here.

**Validated.** `results/raw/long_range_dependency_NIAH_qwen3_0.6b_db8099fc714c.jsonl`;
the join counts reproduce by migrating `results/raw/*.jsonl` in memory.

**Implies.** Three things.

1. **J-004 is answerable now, for the first time.** "Do different models fail
   on the same inputs?" has six shared design points across `qwen3:0.6b` and
   `qwen3:4b` — a small baseline, but a real one, and it grows with every run
   from here. Note it is a `case_key` join: these runs predate
   `case_fingerprint`, so the claim is "same nominal cell", not "same bytes"
   (D-012).
2. The 402-record archive now migrates cleanly to one shape, which is the
   first time anything has read it back end to end. J-005's three shapes all
   survive the walk.
3. The `done_reason` audit stays open and needs a run that reproduces the
   dangling-output mode — a weaker model, or the same `llama3:8b` sweep on a
   host that has it. Until then J-011's five cases keep their stated cause,
   flagged as unconfirmed.

**Disposition.** note — the tokenizer figure graduates to LIMITATIONS §1.1 as
the first measured bound once a second model family is measured.

---

## J-016 — `--kv-cache-type q8_0` configures nothing and mislabels the record
Status: open — diagnosis stands, prescription withdrawn by J-018

**Observed.** The flag exists, is documented, and has no effect on the model
server. Grepping the whole package for the variable that actually controls KV
precision finds it only in a help string and a printed hint:

```
$ grep -rn "KV_CACHE_TYPE\|FLASH_ATTENTION" src/ scripts/
src/probebench/cli.py:149:  "KV cache precision assumed when estimating memory. Set OLLAMA_KV_CACHE_TYPE to match."
src/probebench/experiments/long_range_dependency/NIAH/run.py:295:
    "  - set OLLAMA_FLASH_ATTENTION=1 and OLLAMA_KV_CACHE_TYPE=q8_0, "
```

The flag's only consumer is the memory estimator:

```
src/probebench/cli.py:735:  kv_cache_bytes_per_element=1 if args.kv_cache_type == "q8_0" else 2
```

`kv_cache_bytes_per_element` feeds `estimate_case_bytes` and nothing else. It
is written into every record as `generation.kv_cache_bytes_per_element`.

**Expected.** That `--kv-cache-type q8_0` causes generation to run with a
q8_0 KV cache.

**Mechanism.** KV precision is a property of the **Ollama server process**,
set by `OLLAMA_KV_CACHE_TYPE` in its environment (and requiring
`OLLAMA_FLASH_ATTENTION=1` in llama.cpp). ProbeBench is an API client; it
cannot change the precision of an already-running server, and it never reads
the variable to find out what the server is doing.

So the flag means "assume q8_0 **when estimating memory**", which is what the
help string says if read carefully, and what `run.py:295` hints at by telling
the user to set the env var themselves. The defect is not that the flag lies
about its own scope — it is that **the assumption is then written into the
record as though it were a fact about the run.**

A run invoked with `--kv-cache-type q8_0` and the env var unset therefore
generates at f16 and archives `kv_cache_bytes_per_element: 1`. Nothing in the
record distinguishes that from a genuine q8_0 run.

**Validated.** The greps above; `cli.py:735` is the only assignment.

**Implies.** Three things.

1. **The planned q8_0-vs-f16 experiment cannot run until this is fixed.** Its
   whole design is a paired comparison of the same `case_fingerprint` under two
   KV precisions; if the flag does not set the precision, both arms are f16 and
   the experiment measures noise while appearing to measure quantisation.
2. The right fix is not to *set* the variable — a benchmark that mutates its
   server's environment mid-flight is worse. It is to **read** it, cross-check
   it against the flag, and refuse when they disagree. The server is the
   ground truth; the flag is a claim about the server.
3. `generation.kv_cache_bytes_per_element` should be renamed or joined by
   `kv_cache_type_effective`, so the *estimator's assumption* and the *run's
   actual precision* are separately recorded. Today one field carries both
   meanings and is only ever the first.

No archived record is affected in practice — every run so far used the default
f16 and the env var was unset, so assumption and reality coincided. The
exposure is entirely forward.

**Disposition.** limitation — a new LIMITATIONS entry under §1, since it is a
threat to any future claim about KV precision rather than engineering debt.

---

## J-017 — qwen3 thinks by default, unrecorded; and `think=False` leaks the chain of thought
Status: open

**Observed.** `models/ollama.py` never passes `think` to `client.chat`, so
generation runs at the model's default. Measured directly against the live
server with the benchmark's own system prompt:

```
qwen3:0.6b  default      eval=175  thinking=675 chars   content='ALPHA-9921-X'
qwen3:0.6b  think=True   eval=158  thinking=590 chars   content='ALPHA-9921-X'
qwen3:0.6b  think=False  eval=  9  thinking=0           content='ALPHA-9921-X'

qwen3:4b    default      eval=241  thinking=980 chars   content='ALPHA-9921-X'
qwen3:4b    think=True   eval=259  thinking=1065 chars  content='ALPHA-9921-X'
qwen3:4b    think=False  eval=259  thinking=0           content="Hmm, the user wants me to act as
                                                                 a precise extraction engine..."
```

**Expected.** Nothing in particular — `think` had never been examined. That is
the point of the entry.

**Mechanism.** Three separate findings.

*Thinking is on by default and is discarded.* Every qwen3 record in the
archive was produced with 175–241 decode tokens of hidden reasoning that was
never recorded and never counted anywhere except inside `eval_count`. That is
an unversioned measured variable of exactly §1.12's class: a run cannot state
whether it reasoned. It is also most of the generation cost at long context,
since every decode token attends over the entire KV cache.

*`think=False` does not disable thinking on the 4B — it relocates it.* The
`thinking` field goes empty while `eval_count` stays at 259, and the reasoning
reappears **inside `message.content`**. On the 0.6B the same flag works
cleanly (9 tokens, bare answer). So the flag's behaviour differs between two
models of the same family on the same server — a serving-stack result obtained
in about a minute.

*The judge is unaffected, and that is not luck.* `OllamaJudge` passes
`think=False` **and** `format="json"`, and the structured-output constraint
suppresses the leak:

```
judge, think=False  eval=43  thinking=0     content='{\n "score": 1.0, "grounded": true, ...'
judge, think=True   eval=45  thinking=4488  content='{\n "score": 1.0, "grounded": true, ...'
```

`format="json"` is doing the work. The judge's `think=False` is a genuine
saving of ~4,500 characters of reasoning per case and should stay.

**Validated.** The two tables above, run against `localhost:11434` with
`build_judge_system_prompt` / `build_judge_prompt` for the judge rows.

**Implies.** Four things.

1. **`think=False` must not be used as a generation cost lever.** On the 4B the
   leaked chain of thought lands in the string every evaluator scores: it would
   pass `lexical_exact_match` (contains the code, no repudiation), crater
   `semantic_similarity` (§1.5 — the metric is length), and confuse the judge.
   A stray `</think>` in `content` is, conversely, a free deterministic
   `FORMAT_VIOLATION` rule for the rule tier.
2. Thinking should be **passed explicitly and recorded**, keeping the current
   default (on) so archived comparability is preserved, with
   `len(message.thinking)` captured as evidence. Changing the default would
   change what is measured; recording it does not.
3. This is a second instance of the pattern behind §1.12: a decision that
   moves the numbers, taken by a default nobody chose, invisible in the record.
   The first was the judge prompt. Both were found by looking at what the
   provider returns rather than at what we send.
4. It partly explains long-context latency. At 32k, qwen3:4b takes 201 s/case
   and a large share of that is decoding ~250 reasoning tokens against a 4.5
   GiB KV cache. Any cost model that ignores thinking will under-predict.

**Disposition.** limitation — §1.12 should widen from "the judge prompt is an
unversioned measured variable" to cover generation-side sampling settings, and
the `think=False` leak deserves its own entry as a trap.

---

## J-018 — KV precision is measurable from the API; J-016's proposed fix was wrong
Status: open — corrects J-016's `Implies` §2

**Observed.** J-016 concluded that the fix for the mislabelled `q8_0` flag was
to *read* `OLLAMA_KV_CACHE_TYPE` and cross-check it against the flag. Checking
how Ollama actually runs on this machine disproves that:

```
$ systemctl is-active ollama            -> active
$ ps -o pid,user,cmd -C ollama          -> 922  ollama  /usr/bin/ollama serve
$ cat /proc/922/environ                 -> Permission denied
```

The server runs as a **systemd service under user `ollama`**. Our shell's
environment is a different process's environment, and the server's is not
readable without root. So "read the env var" answers a question about the
wrong process.

Then, unexpectedly: `/api/ps` reports each loaded model's `size` **and its
actual `context_length`**. Loading one model at two context sizes and taking
the difference cancels weights and compute buffers, leaving the KV cache:

```
qwen3:0.6b (28 layers, 8 KV heads, head_dim 128)

size @  4,096 = 1,034,975,968
size @ 16,384 = 2,396,321,218
delta         = 1,361,345,250 B over 12,288 tokens
              = 110,787 B/token = 108.2 KiB/token

bytes_per_element = 110,787 / (2 x 28 x 8 x 128) = 1.932
```

Against a true f16 value of **2.0**.

**Expected.** J-016 expected the environment to be the ground truth. It is
not; it is not even readable.

**Mechanism.** Two.

*Why the env approach fails.* KV precision is a property of the `llama-server`
process that Ollama spawns, configured from the Ollama daemon's environment.
ProbeBench is an HTTP client of that daemon. On the default install — Arch,
Ubuntu, macOS — the daemon is a service under its own user, so there is no
path from our process to its configuration. Setting the variable in our shell
changes nothing; reading it tells us nothing. Recording it would produce a
confident, checkable-*looking* field unrelated to the run, which is worse than
recording nothing — the same failure D-013 avoided for hardware.

*Why the differential measurement works.* Reported `size` is
`weights + compute buffers + KV(ctx)`. The first two do not depend on context
length, so differencing two loads of the same model eliminates them exactly,
and the residual is `kv_bytes_per_token x delta_ctx`. Dividing by the known
GGUF geometry `2 x n_layers x n_kv_heads x head_dim` isolates
`bytes_per_element`. **This uses R-001's validated KV model as a measuring
instrument rather than as a predictor**, which is a use it was not built for
and is the interesting part of the entry.

It also works in the regime this fleet runs in: `size_vram` was only 37 MB of
the 1.03 GB above, so the cache was overwhelmingly in system RAM and the
measurement was unaffected.

**Validated.** The commands above, against `localhost:11434`, Ollama 0.32.9.
The 3.4% shortfall from 2.0 is **unexplained** — the leading hypothesis is a
per-context overhead that does not scale purely linearly with `num_ctx`, but
it has not been isolated. It does not threaten the f16/q8_0 decision, since
those hypotheses are 2x apart and the observed error is 3%.

**Implies.** Four things.

1. **J-016's stated fix is withdrawn.** The env var is not the ground truth
   and on the default install is not even observable. That entry's diagnosis
   of the *bug* stands; its prescription does not.
2. The correct fix measures rather than asks, and therefore works remotely,
   works against a service-managed daemon, and works when someone else
   configured the machine. All three matter for a three-machine fleet where
   two boxes are not ours.
3. This is a direct measurement of the **serving stack**, which is CLAUDE.md's
   fourth question and the one nothing in the repo answers. J-016 read as a
   labelling defect; it is better read as a missing instrument.
4. The probe can report a value the configuration cannot express. §2.6 notes
   `kv_cache_bytes_per_element` is an `int`, so a `q4_0` server would measure
   ~0.5 and have nowhere to be recorded. That limitation was theoretical; the
   probe makes it reachable.

**Disposition.** limitation and publishable — the measurement technique is
small, general, and reusable by anyone benchmarking against Ollama.

---

## J-019 — Six runs exist only as a gitignored log file
Status: open

**Observed.** Auditing whether `results/raw/*.log` is needed at all, before
deleting them:

```
$ ls results/raw/*.log | wc -l
51
$ du -ch results/raw/*.log | tail -1
204K

$ grep -l "Skipped" results/raw/*.log | wc -l
6
$ grep -h "Skipped" results/raw/*.log | head -1
WARNING ...run: Skipped 5 of 5 planned cases (context ceiling 8000).
                Targets dropped: [64000]
```

Every one of those six runs has **no `.jsonl` at all**:

```
long_range_dependency_NIAH_qwen3_4b_2f685cb2810a.log   jsonl=MISSING
long_range_dependency_NIAH_qwen3_4b_6aed0d8bc512.log   jsonl=MISSING
... (6 of 6)
```

Nothing in the codebase reads a `.log`; `run.py:54` only writes one. And
`results/raw/` is in `.gitignore`, so none of this is under version control.

**Expected.** That the logs were redundant with the JSONL and could be
deleted without loss.

**Mechanism.** Two gaps compose into one.

A case that exceeds the context ceiling is **dropped before generation**, so
it never becomes a `BenchmarkResult` and never reaches the JSONL writer. The
only trace is `NiahBenchmark.skipped`, which `run.py` renders as a log
WARNING and then discards.

When *every* case is skipped — a `--context 8000` ceiling against a 64,000
target — the run produces zero results, and `JSONLWriter` creates the file
lazily, so no `.jsonl` is written at all. The run's entire existence is one
WARNING line in an untracked file.

So **invariant 4 — "Skipped cases must always be reported, never silently
dropped" — is currently upheld only by a gitignored log**. It is satisfied in
the letter (something is printed) and broken in the spirit (nothing is
recorded).

**Validated.** Commands above. Cross-checked that `results/raw/` matches
`.gitignore:80`, and that `grep -rn "\.log" src/ scripts/ tests/` finds only
the writer.

**Implies.** Three things.

1. The *files* are disposable — 45 of 51 duplicate what the JSONL already
   holds, they are untracked, and nothing consumes them. The *logging* is
   not: for a two-phase run that crashes mid-generation (§4.1 — nothing is
   written until phase 1 completes) the log is the only artifact that the run
   ever happened.
2. **Skips need to be data, not a log line.** The natural home is a run-level
   sidecar next to the JSONL — the same place the resolved config will go —
   recording each skipped cell and its reason. Until then, any statement of
   the form "the sweep covered N cells" is unverifiable from the archive.
3. This is the second time a run-level fact has had nowhere to live; the
   first was the host block (D-013), which got a per-record home because it
   applies to every case. Skips apply to *absent* cases, so they cannot go in
   a per-record block, which is exactly why they fell through.

**Disposition.** limitation — a new LIMITATIONS entry, since it undermines
invariant 4 and makes sweep coverage unverifiable.

---

## J-020 — The judge forgives exactly what the model was told not to do
Status: open

**Observed.** Run `81e709779b80` (`qwen3:0.6b` at 32k, depths 0.1/0.5/0.9, six
needles, judge `qwen3:4b`). A user reading the output flagged entry 8 as
scored too generously:

```
needle    : The magic word to unlock the door is CRIMSON-EAGLE-44.
predicted : The important secret mentioned in the text is the magic word to
            unlock the door, which is **CRIMSON-EAGLE-44**.
lexical   : 1.0     llm_judge : 1.0     grounded : true
```

Every one of those scores is defensible on its own terms — the code is
asserted, and the framing is a near-verbatim restatement of the needle, so it
is genuinely grounded. But the model's **system prompt** was:

```
You are a precise extraction engine.
Answer ONLY with the secret code found in the text.
Do not add any explanation.
```

The response is a full sentence with markdown emphasis. It disobeys the
instruction it was given, and **nothing in the pipeline measures that.**

Counting the whole run:

```
bare code only : 9/18
added framing  : 9/18   <- every one scores llm_judge 1.0 (bar the one wrong answer)
```

**50% of the run violates the output contract and the benchmark reports 94%
accuracy.**

**Expected.** That "answer ONLY with the code" was being enforced by something.
It is not enforced by anything.

**Mechanism. This is self-inflicted, and recent.** R-003 fixed the judge
penalising correct-but-verbose answers (J-007: `semantic_similarity` ranked
brevity, and the judge was scoring framed answers 0.0). The fix added a clause
to the judge prompt:

> "The response may restate the answer inside a full sentence, add framing, or
> use markdown emphasis. **None of that is an error.** Judge only whether the
> expected answer is present and correct; do not penalise a correct answer for
> being verbose."

So the *generation* contract says "code only, no explanation" and the
*judging* contract says "framing is not an error". Two prompts, opposite
requirements, written weeks apart, and the judge enforces the one the model
was never shown.

Neither clause is wrong in isolation. The verbosity clause fixed a real defect
and should stay. The bug is that **instruction-following was silently
reclassified as noise** while the instruction remained in the system prompt.

A related gap fell out of the same check: `system_prompt` is popped by the
runner and is **not in the record**. `system_prompt_sha256` is in the
fingerprint, so a change is detectable, but a reader cannot see what the model
was actually told. The instruction is a measured variable with no readable
provenance.

**Validated.** Counts above from the stored file; the two contradicting texts
are quoted verbatim from `judge/prompt.py:27-30` and `NIAH/settings.py:34`.

**Implies.** Four things.

1. **This is `FORMAT_VIOLATION`, and it is the first label with a usable base
   rate.** The planned taxonomy defines it as "content correct, output
   contract violated" — exactly this. `grounded` fired on 1 of 44 (J-010);
   this fires on **9 of 18**. A label tier can finally be validated against
   something that actually occurs.
2. It is rule-decidable and needs no model call: compare the response, modulo
   whitespace and markdown, against the expected string. Free, deterministic,
   replayable over stored JSONL — which is what build-order step 4 requires.
3. **It must not be folded into `llm_judge`.** Correctness and compliance are
   different questions, and a single float that drops when a model is chatty
   is precisely the defect J-007 recorded for `semantic_similarity`. Two
   fields, not one number.
4. It reopens a question the project has never answered: **is NIAH measuring
   retrieval, or retrieval-plus-instruction-following?** The system prompt
   currently asserts the second while every metric measures the first. Either
   the instruction should be relaxed to match what is scored, or compliance
   should be scored to match what is instructed. Both are defensible; the
   present state is neither.

**Disposition.** limitation, and a decision — the choice in (4) changes what
NIAH measures and must be recorded before either fix lands.

---

## J-021 — 85% of the archive disobeys the instruction, and one model disobeys it always
Status: open — the per-model contrast is `Validated: not yet` (confounded with context length, see J-022)

**Observed.** Following J-020, a compliance rule was replayed over the whole
archive: does the response consist of the expected code alone, tolerating
markdown, surrounding quotes and a trailing period? The system prompt says
*"Answer ONLY with the secret code found in the text. Do not add any
explanation."*

```
archive: 424 responses   compliant 64   VIOLATIONS 360  (85%)

  llama3:8b      330/330  violations  (100%)
  llama3.2:1b      6/6    violations  (100%)
  qwen3:0.6b      24/51   violations  ( 47%)
  qwen3:4b         0/37   violations  (  0%)
```

**Expected.** J-020 measured 9/18 on one run and I assumed that was
representative. It is not: the archive-wide rate is 85%, and the spread
between models is total.

**Mechanism.** Not yet established, and the difference between models is the
interesting part rather than the rate itself.

`qwen3:4b` obeys the instruction in **37 of 37** cases. `llama3:8b` obeys it
in **0 of 330**. Those are not nearby numbers with noise between them; they
are opposite corners. Whatever this measures, it separates these two models
far more sharply than retrieval accuracy does — `llama3:8b` retrieved
correctly in 74% of cases while complying in none of them.

Candidate explanations, none tested: instruction-following capability differs
by model family; RLHF/chat tuning pushes some models to always frame an
answer; the system prompt is being weighted differently by different chat
templates; or the models were not all given the same instruction.

**The last one cannot currently be ruled out, and that is a finding in
itself.** `system_prompt` is popped by the runner and is not in the record
(J-020). The `llama3` runs predate `case_fingerprint`, so they carry no
`system_prompt_sha256` either. **There is therefore no way to verify from the
archive that `llama3:8b` was given the same instruction as `qwen3:4b`.** The
100%-vs-0% contrast is real in the data and unattributable from it.

**Validated.** Rule replayed over 424 archived responses through
`migrate_record`. The rule is deliberately lenient — it accepts `**CODE**`,
`"CODE"` and `CODE.` as compliant — so 85% is a *lower* bound on violations
under a stricter reading.

**Implies.** Four things.

1. **Instruction-following is a larger effect than anything else measured in
   this project.** Retrieval accuracy spans roughly 74–100% across the
   archive; compliance spans 0–100%. If NIAH scores retrieval *and*
   instruction-following (the decision recorded in D-018), the headline
   number for `llama3:8b` goes from ~74% to **0%**, and that is not a rounding
   change — it is a different result.
2. This is the base rate the taxonomy needed. `grounded` fired on 1 of 44;
   `FORMAT_VIOLATION` fires on 360 of 424, with a clean per-model split. A
   label that separates models is worth more than one that fires rarely.
3. **The provenance gap has to close before any claim rests on this.** Until
   `system_prompt` is in the record, "llama3:8b never obeys the instruction"
   and "llama3:8b was never given the instruction" are indistinguishable.
   That is the difference between a model result and a bug in our harness.
4. It reframes what the benchmark has been reporting. Every accuracy figure
   in this project so far has silently scored a task the models were not
   asked to perform — retrieval alone — while instructing them to perform a
   different one.

**Disposition.** publishable, once (3) is closed. The per-model contrast is
the strongest single result in the archive, and it was found by a user reading
one response and asking why the judge liked it.

---

## J-022 — `semantic_similarity` was an exact format detector all along, and there is a degradation curve
Status: open

**Observed.** Replaying a form-based compliance rule over the whole archive
(424 records, through `migrate_record`) and cross-tabulating it against the
metrics already stored:

*Compliance separates perfectly on `semantic_similarity`:*

```
answer form = bare : n= 64   min 0.9918   mean 0.9995
answer form = prose: n=360   max 0.7977   mean 0.6342
                             ------------------------
                             gap +0.1941, ZERO overlap
```

It holds *within* `qwen3:0.6b`, the only model with both classes —
min(bare) 0.9918 against max(prose) 0.7957 — so it is not a model artefact.

*The retrieval × form 2×2:*

```
              bare    prose
retrieved      64      282
not retrieved   0       78     <- "bare but wrong" is EMPTY
```

*Compliance by model and context length:*

```
  qwen3:4b      4,000   34/34  = 100.0%
  qwen3:4b     32,000    3/3   = 100.0%
  qwen3:0.6b    4,000   14/14  = 100.0%
  qwen3:0.6b   32,000   12/27  =  44.4%
  qwen3:0.6b   36,000    1/5   =  20.0%
  qwen3:0.6b   40,000    0/5   =   0.0%
  llama3:8b     7,000     0/66 =   0.0%   (identically 0% at 7250/7500/7750/8000)
  llama3.2:1b 128,000     0/6  =   0.0%
```

**Expected.** J-021 read the per-model rates as a clean model effect. Two of
the three findings here contradict or sharpen that.

**Mechanism.** Three separate things.

*1. §1.5 has the diagnosis half right and the conclusion wrong.* It records
that `semantic_similarity` "discriminates on response length, not
correctness", which is true and was treated as a defect. What the separation
above shows is stronger: it is not noisily length-sensitive, it is a **near-
perfect binary detector of response form**, with a 0.19 gap and no overlap in
424 records. Embedding a whole response against a bare 12-character code
produces ~1.0 when the response *is* that code and ~0.6–0.8 when it is a
sentence. That is a step function, not a gradient.

So the metric was measuring something real and useful, under a name that reads
as correctness. It was never a good correctness metric and is now redundant as
a form metric, because an exact free rule does the same job — but "broken" was
the wrong word for it.

*2. The "bare but wrong" cell is empty, and that constrains the rule's
definition.* Zero records in 424. A compliance rule defined as "the response
equals the expected string" would therefore make compliance *imply* retrieval:
the composite `retrieved AND complied` would collapse algebraically to
`complied`, and that cell would be unreachable **by definition** rather than
merely unobserved. Defining compliance on **form alone**, never referencing
`expected`, costs nothing — both definitions score all 424 records identically
today — and keeps the cell reachable so a reachability audit can record it
honestly.

*3. The cross-model contrast is confounded with context length.* `qwen3:4b` is
34 of 37 records at 4k; `llama3:8b` is all 330 at 7–8k; there is no context
overlap between them at all. Meanwhile **within** `qwen3:0.6b` compliance runs
100% → 44% → 20% → 0% across 4k → 32k → 36k → 40k, so the within-model spread
is as total as the between-model spread. The one genuinely matched cell is
32k, where `qwen3:4b` is 3/3 and `qwen3:0.6b` is 12/27 — a real model effect
at n=3.

**Validated.** Independently recomputed from `results/raw/*.jsonl` rather than
taken from the analysis that suggested it; numbers above are that recomputation.

**Implies.** Four things.

1. **CLAUDE.md's "every metric in every successful run has been 1.0 … the
   benchmark has no discriminating power" is false.** The 100%→0% compliance
   curve on `qwen3:0.6b` is a graded, monotone degradation in context length —
   the first this project has produced. It was there in the archive the whole
   time, inside a column labelled `semantic_similarity`.
2. **D-006 can close.** It stayed open partly on "dropping it loses the only
   continuous signal". The signal was never continuous; it is bimodal with a
   0.19 gap, and an exact offline rule replaces it at zero cost.
3. §1.5 needs correcting from "discriminates on length" to "is an exact
   detector of response form" — a stronger and more useful statement.
4. **J-021's headline needs downgrading to `Validated: not yet`.** "The spread
   between models is total" is not supportable without a context-matched
   comparison, and the archive has one cell of n=3.

**Disposition.** publishable — a metric that was a defect under one task
definition turns out to be a validated instrument under another, and the
degradation curve is the first real result.

---

## J-023 — The thinking channel is not hiding the framing
Status: open

**Observed.** §1.17 raised the possibility that qwen3's high
`instruction_compliance` is an artefact: qwen3 emits reasoning into
`message.thinking`, which never reaches `predicted`, while llama3 has no such
channel (J-017). If qwen3 were *framing into the discarded channel* and
emitting bare content, the cross-family contrast would measure where a model
puts its prose rather than whether it obeys.

Probing directly, one needle at 4k with the benchmark's own system prompt:

```
qwen3:0.6b  think=True   verdict=exact   content=  12 chars  thinking= 391
qwen3:0.6b  think=False  verdict=exact   content=  12 chars  thinking=   0
qwen3:4b    think=True   verdict=exact   content=  12 chars  thinking=1108
qwen3:4b    think=False  verdict=prose   content=1093 chars  thinking=   0
```

**Expected.** If the channel were absorbing the framing, removing it should
push the prose into `content` and flip the verdict to `prose`.

**Mechanism.** It does not, for `qwen3:0.6b`: with thinking off the response
is still the bare 12-character code. **The compliance survives removal of the
channel**, so the channel is not where the framing was going.

The `qwen3:4b` `think=False` row looks like a flip but is not evidence. It is
J-017's leak: on the 4B, `think=False` does not disable reasoning, it relocates
the chain of thought into `content`. The 1,093 characters scored `prose` are
raw CoT, not a framed answer. That arm cannot test this question at all.

Both models' `thinking` does contain the phrases that constitute framing in
non-compliant responses ("important secret", "mentioned in the text") — but as
*reasoning about the question*, not as a framed answer awaiting emission. The
distinction matters: the confound requires the model to have composed a framed
answer and hidden it, and what is in the channel is deliberation.

**Validated.** Probe above against `localhost:11434`, one needle, 4k, both
models, both settings.

**Implies.** Three things, and the third is the one that survives.

1. §1.17's thinking-channel confound is **not supported for `qwen3:0.6b`**.
   The measurement is not an artefact of a hidden channel.
2. It is **untestable on `qwen3:4b`** while `think=False` leaks. Testing it
   there needs a model whose reasoning can actually be disabled, or a serving
   stack that does not leak.
3. **The remaining asymmetry is real but is not a measurement bug.** qwen3's
   `predicted` is produced *after* a reasoning pass; llama3's is not. If
   reasoning improves instruction-following, that is a genuine capability
   difference between the systems under test, not an instrument artefact — and
   it is exactly the kind of thing a benchmark should surface rather than
   control away. What it does mean is that any cross-family compliance claim
   must state the thinking configuration, which schema 1.3 now records.

**Caveat that keeps this open.** The probe ran at 4k, where `qwen3:0.6b` is
100% compliant in the archive anyway. The interesting regime is 32k, where it
is 44%, and this test has not been run there. A repeat at 32k would cost
~17 minutes and is the natural completion.

**Disposition.** note — narrows §1.17 from three candidate confounds to two,
and removes the one that would have invalidated the measurement rather than
merely complicated it.

---

## J-024 — Both scoping controls pass, and both of my predictions were wrong
Status: open

**Observed.** The plan's Phase 2 controls, run at 1,000 tokens before
committing to either experiment.

*Counting* — k needles evenly spaced, "how many secret access codes appear in
the text?", answer scored against k:

```
qwen3:0.6b   k=1..8:  OK OK OK OK MISS(8) OK MISS(8) MISS(10)   -> 5/8
                      k<=5: 4/5 = 0.80

qwen3:4b     k=1..8:  OK OK OK OK OK OK  prose  OK              -> 7/8
                      k<=5: 5/5 = 1.00
```

*Multi-hop* — a `[POINTER]` block names a place, four `[REGISTRY]` blocks each
give one place's code, so the answer is reachable only by composing two hops.
Decoys are the whole design: without them a model returning the only code
present would look like it had composed:

```
qwen3:0.6b   3/4 retrieved, 4/4 compliant
             the miss returned a DECOY (OMEGA-7732-Q for DELTA-1102-M)
qwen3:4b     4/4 retrieved, 4/4 compliant
```

**Expected.** I predicted counting would fail for `qwen3:0.6b` and that
`qwen3:4b` would pass only to k ≤ 4. I argued at length in the plan that
multi-hop should be **dropped** — that two-hop composition on 0.6B–4B models
would floor at zero, that a saturated floor is as uninformative as J-003's
saturated ceiling, and that context length would become a nuisance parameter.

**Both predictions were wrong, in the same direction: I underestimated the
models.** Counting holds to k=8 on the 4B and k=4 on the 0.6B. Multi-hop is
4/4 and 3/4 at 1k. The decision rules written before the data — counting
survives unless k ≤ 5 accuracy is below 0.8; multi-hop survives if the largest
fleet model clears 0.7 — are met by both, and multi-hop is met decisively.

**Mechanism.** Nothing surprising in the passes. Two things in the failures
are worth more than the pass rates.

*`qwen3:4b` at k=7 answered* **`"The text contains seven instances of the..."`**
— content correct, format violated, and my integer-extractor concatenated the
digits of unrelated codes into a 33-digit number and scored it a miss. The
counting control independently reproduced the exact retrieval-versus-compliance
split that D-018 exists for, and a naive scorer conflated the two. That is the
third time this pattern has appeared under a different name.

*The one multi-hop miss returned a decoy*, not a fabrication and not a refusal.
`niah.distractor_retrieval` — the label CLAUDE.md still calls "unreachable by
construction" — is reachable in a four-line control, identifiable from the
response, and rule-decidable because we know the full inventory.

**Validated.** Scratch scripts against `localhost:11434`, 1,000-token
haystacks, temperature 0. The counting run was killed by a timeout after
`qwen3:4b` k=6 and the last two cases were re-run separately; the numbers
above are complete.

**Implies.** Four things.

1. **Both experiments are worth building.** The refusals the plan prepared for
   are not needed, and the decision entry records an acceptance instead.
2. **Multi-hop is the stronger of the two**, which inverts my ranking. It
   produces a decoy return — a *diagnosable* failure with a known cause — where
   counting produces an off-by-N whose cause is opaque. The decoy is exactly
   the evidence the rule tier was designed to consume.
3. Both controls must carry a compliance column from the start. The k=7 case
   shows a content-correct answer being scored a miss by a format-blind
   scorer, which is D-018's whole argument arriving unprompted in a different
   task.
4. A caution on scope: both controls ran at **1,000 tokens**, where compliance
   is 100% and retrieval is near-perfect. That is the point of a control — it
   establishes a ceiling exists — but it says nothing about whether either
   task degrades with context, which is the actual experiment.

**Disposition.** note, and a decision — D-020 records the acceptance with the
conditions that would reverse it.

---

## J-025 — The KV probe caught a silent misconfiguration on its first real use
Status: open

**Observed.** The daemon was reconfigured for `q8_0` KV cache and restarted, in
order to run the paired f16-vs-q8_0 experiment. The probe disagreed:

```
$ env | grep -iE "OLLAMA_KV|OLLAMA_FLASH"
  (nothing set in our shell)

bytes_per_element : 2.0804
classified as     : f16
evidence          : 930,401,484 @4096  ->  2,396,321,218 @16384
```

Both byte counts are **identical** to the pre-restart measurement, which is
what made it obvious something had not changed. Then:

```
$ systemctl show ollama -p Environment
Environment=HOME=/var/lib/ollama OLLAMA_MODELS=/var/lib/ollama

$ systemctl show ollama -p ActiveEnterTimestamp
ActiveEnterTimestamp=Tue 2026-09-08 22:11:07 IST     (four minutes earlier)

$ cat /etc/systemd/system/ollama.service.d/override.conf
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_FLASH_ATTENTTION=1
```

**Expected.** D-017 predicted the probe would move to ~1.0 once the daemon was
reconfigured. It did not, and the reason is that the daemon was not
reconfigured.

**Mechanism.** Two independent faults in one four-line file.

*The drop-in has no `[Service]` section and no `Environment=` prefix.* A
systemd drop-in is an INI file; bare `KEY=VALUE` lines belong to no section and
are ignored. `systemctl show` confirms only the two variables from the packaged
unit survive. The service restarted cleanly, so nothing anywhere reported an
error.

*`OLLAMA_FLASH_ATTENTTION` has a doubled T.* Even with the syntax repaired,
that line would export a variable nothing reads — and `q8_0` KV requires flash
attention in llama.cpp, so the cache would have silently stayed f16 a second
time for a second reason.

**Validated.** The three commands above. The identical byte counts across a
restart are the strongest single signal: a genuine precision change halves the
per-token slope, and this moved by nothing at all.

**Implies.** Three things, and the first is why the probe exists.

1. **Every alternative design would have failed silently here.** Trusting the
   flag would have archived 540 records labelled `q8_0` that ran at f16 — the
   original J-016 defect, in the exact experiment built to depend on it.
   Reading *our* environment would have found it empty and concluded nothing,
   since we never set it. Reading `/proc/<pid>/environ` is permission-denied
   for a service running as user `ollama`. Only measuring the daemon's actual
   memory behaviour detected it.
2. **The refusal is the load-bearing half.** Had the run proceeded with
   `--kv-cache-type q8_0`, the mismatch check would have stopped it before a
   single record was written. That path is now confirmed against a real
   misconfiguration rather than a synthetic one.
3. It is a reminder that "I changed the config and restarted" is a claim, not a
   fact, and that a service restarting successfully says nothing about whether
   it read what you wrote. The general form is the same as J-016's: the gap
   between intent and effect is where silent corruption lives.

**Disposition.** publishable — this is the payoff paragraph for the
"flag that configured nothing" article, which currently ends on a design
argument and can now end on the design catching something real.

---

## J-026 — q8_0 is 1.0625 bytes/element, not 1.0, and the probe reads bimodally
Status: open

**Observed.** With the daemon correctly configured for `q8_0` (J-025's
override repaired; `systemctl show` lists all four variables), the probe was
run four times against `qwen3:0.6b`:

```
during the 90-case run:  1.0315 B/elem  -> classified q8_0
repeat 1:                1.0315 B/elem  -> classified q8_0
repeat 2:                1.1935 B/elem  -> classified None ("unrecognised")
repeat 3:                1.1935 B/elem  -> classified None
```

Two values, repeated exactly, with nothing in between. This is not gaussian
measurement noise.

**Expected.** A single value near 1.0, the nominal size of an 8-bit element,
which is what `KV_TYPES` encodes.

**Mechanism.** Two separate faults, and the first is mine.

*`KV_TYPES` used nominal bit-widths where ggml uses block quantisation.* A
`q8_0` block holds 32 values at one byte each **plus a 2-byte fp16 scale**:

```
q8_0:  (32 x 1 + 2) / 32 = 34/32 = 1.0625 B/element
q4_0:  (32 x 0.5 + 2) / 32 = 18/32 = 0.5625 B/element
f16:                                 2.0    B/element
```

So the true q8_0 constant is **1.0625**, 6.25% above what the table said. With
a +/-15% band centred on 1.0 the acceptance window was [0.85, 1.15] — which
excludes a correct reading of 1.19 and, worse, sits off-centre on the true
value. Centring on 1.0625 gives [0.903, 1.222], which accepts both observed
readings, and the three bands still do not overlap.

*The probe itself is bimodal, not noisy.* 1.0315 and 1.1935 differ by 15.7% and
each repeats exactly. The reported `size` evidently depends on some discrete
state — most plausibly how much of the model is resident in VRAM versus system
RAM at the moment of the load, which changes when another model is also
resident. Both readings bracket the true 1.0625 (-2.9% and +12.3%).

**Validated.** Four probes; the ggml block layout is arithmetic, not
measurement. The f16 readings from J-018 and J-022 (1.932, 2.080) bracket 2.0
the same way, at -3.4% and +4.0% — so the bimodality is present in both regimes
and was simply narrower than the band on f16, which is why it went unnoticed.

**Implies.** Four things.

1. **The 90-case q8_0 run is valid.** It measured 1.0315 and recorded
   `kv_cache_type_effective: "q8_0"` — a verified q8_0 arm, not an assumed one.
   It needs a matching f16 arm to become the paired comparison.
2. `KV_TYPES` must carry the block-quantised constants. This is a correctness
   fix, not a tolerance widening: the old centre was simply the wrong number.
3. **The refusal has a hole that this exposed.** A run whose measurement lands
   outside every band classifies `None`, and the mismatch check only fires when
   `kv_type is not None`. So the two 1.1935 readings would have let a run
   proceed *unverified* while labelled `q8_0`. Conservative in one sense —
   unrecognised is not evidence of mismatch — but it means "measured" in the
   record can mean "measured and not understood". The probe field says
   `measured` either way, which understates the uncertainty.
4. The bimodality bounds the instrument more tightly than §2.7 states: it is
   not +/-8% gaussian, it is two discrete states about 16% apart. Fine for
   telling f16 from q8_0 from q4_0 (bands are 2x apart); useless for anything
   finer, and a single reading should never be quoted as a precise figure.

**Disposition.** limitation — corrects §2.7's noise characterisation, and the
`None`-classification hole needs closing so an unrecognised measurement is
visibly not a verification.

---

## J-027 — It was context length, not model family. Compliance collapses, and the collapse point is model-specific
Status: open

**Observed.** The context-matched run §1.17 demanded, plus the J-015 audit, on
`llama3:8b` with `qwen3:4b` judging:

```
llama3:8b @ 4,000      n=18   retrieval 100.0%   compliance  50.0%
llama3:8b @ 7-8,000    n=36   retrieval  94.4%   compliance   0.0%
```

Set beside the archive:

```
                4k      7-8k     32k     36k     40k
qwen3:4b       100%       -      100%      -       -
qwen3:0.6b     100%       -       44%     20%      0%
llama3:8b       50%       0%       -       -       -
```

**Expected.** J-021 reported `llama3:8b` at 0/330 and `qwen3:4b` at 37/37 and
read it as a model effect — "the spread between models is total". §1.17 flagged
that the comparison was confounded because the two models shared no context
length.

**The confound was real and the headline was wrong.** `llama3:8b` obeys the
instruction **half the time at 4k**. Its 0/330 in the archive was measured
entirely at 7–8k. What J-021 attributed to model family was mostly context
length.

**Mechanism.** Compliance degrades with context in *every* model measured, and
the collapse point differs by model:

- `llama3:8b` is at 50% by 4k and 0% by 7k.
- `qwen3:0.6b` holds 100% at 4k, falls to 44% at 32k, 0% at 40k.
- `qwen3:4b` holds 100% at both 4k and 32k (n=3 at 32k).

So a **model effect survives, but a partial one**: at a matched 4k, `llama3:8b`
is 50% where both qwen3 models are 100%. That is a real difference and it is
not the 100%-vs-0% separation J-021 claimed. The right framing is not "which
models obey" but **"at what context does each model stop obeying"** — a
collapse point, which is exactly the shape CLAUDE.md's build order wanted from
a length sweep and never got from retrieval.

Retrieval, by contrast, barely moves: 100% at 4k and 94.4% at 7–8k. The two
axes come apart, which is the whole argument for D-018.

**Three secondary findings from the same runs.**

*The J-015 `done_reason` audit is inconclusive, not negative.* All 36 records
are `done_reason: "stop"` — no truncation. But the run **did not reproduce**
J-011's dangling-output mode: the four short responses are complete sentences
("The special key is 8829-BETA-Z."), not the `"...is:"` fragments J-011
recorded. O5's truncation hypothesis is untested rather than disproved, and
reproducing the mode is a precondition for testing it.

*§1.1's front-truncation worry is unfounded for llama-bpe on this corpus.*
Measured expansion is **+0.26%** at nominal 7,000 (7,018 tokens) and **+0.15%**
at 8,000 (8,012) — an order of magnitude smaller than qwen3's +2.5% (J-015),
and 662 tokens inside `num_ctx` 7,680. The archived `llama3:8b` sweep was never
close to truncating, so J-011's failures are not truncation artefacts.

*The non-compliant responses at 4k echo the marker.* Two of the nine:

```
'[IMPORTANT SECRET]: The magic word to unlock the door is CRIMSON-EAGLE-4...'
'The important secret mentioned in the text is:\n\n[IMPORTANT SECRET]: Reme...'
```

The model reproduces the insertion marker verbatim. That is
`niah.needle_verbatim_echo` from the planned taxonomy — a `FORMAT_VIOLATION`
subtype — observed for the first time, and it ties back to J-012: the marker is
a measured variable and models interact with it directly.

**Validated.** Runs `de2cecc1c5b7` (4k, 18 cases) and `7de845de1d9d` (7–8k, 36
cases), single-phase, independent judge, schema 1.4.

**Implies.** Four things.

1. **J-021's per-model claim is withdrawn** and §1.17 is resolved in favour of
   context length, with a residual partial model effect at matched 4k.
2. The reportable result is a **collapse point per model**, not a compliance
   rate. That needs a length sweep per model, which is now the obvious next
   experiment and is cheap for `llama3:8b` (7 s/case, 8k ceiling).
3. `qwen3:4b`'s 100% at 32k is the outlier worth pressing: it is the only
   model that has not collapsed anywhere tested, and it has only 3 records at
   32k. A sweep to its 262k claim is the test.
4. The taxonomy gains an observed label. `needle_verbatim_echo` was
   hypothesised in CLAUDE.md; it is now in the archive with two instances.

**Disposition.** publishable — this is the first result in the project with a
mechanism, a matched control, and a corrected prior.

---

## J-028 — The KV probe silently fails on any model with a window under 16k
Status: open

**Observed.** Both `llama3:8b` runs logged:

```
WARNING: KV cache precision could not be measured (server did not report a
size for the loaded model). Records will say 'f16' was REQUESTED and make no
claim about what ran.
```

Diagnosis:

```
llama3:8b advertised context: 8,192
probe requests num_ctx=16,384 -> /api/ps reports context_length=8192
```

**Expected.** A measurement, as for both qwen3 models.

**Mechanism.** The probe hardcodes `DEFAULT_LARGE_CTX = 16_384` and matches the
`/api/ps` entry on `context_length == num_ctx`. Ollama **clamps** a requested
`num_ctx` to the model's advertised maximum, so for `llama3:8b` it reports
8,192 where the probe expects 16,384, no entry matches, and the probe reports
the generic "did not report a size".

So the probe is broken for **every model with a context window below 16,384** —
which is `llama3:8b`, `mistral:7b`'s shorter variants, and most older models.
It failed safe (no false claim) but the diagnostic message points at the server
rather than at the caller, which is why it read as an Ollama problem.

**Validated.** The clamp reproduced directly: requesting 16,384 for
`llama3:8b` yields `context_length: 8192` in `/api/ps`.

**Implies.** Two things.

1. `large_ctx` must be clamped to the model's advertised context before
   probing, and the failure message must distinguish "the model cannot hold
   the probe's context" from "the server said nothing".
2. `MIN_CTX_DELTA = 8_192` then becomes the binding constraint for short-window
   models: clamped to 8,192, `llama3:8b` gives a 4,096-token separation. That
   minimum was a guess. The defensible criterion is signal size: at 128 KiB per
   token, a 4,096-token delta is **512 MiB** of KV, and telling f16 from q8_0
   means telling 512 MiB from 272 MiB. The bimodal jitter is ~16%, about
   80 MiB. Ample. The minimum should be lowered to 4,096 with that reasoning
   recorded, not left at a number nobody justified.

**Disposition.** limitation — corrects §2.7, which claims three limits and
missed this one.
