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

**Partially measured since schema 1.2.** Records now carry
`response.prompt_eval_count` — the model's own token count for the prompt —
so the error is observable rather than assumed. The first figure (J-015):
`qwen3:0.6b` reports **4,101** tokens for a nominal 4,000 cl100k haystack,
a **+2.5%** expansion.

**llama-bpe measured too (J-027).** `llama3:8b` reports **7,018** tokens for a
nominal 7,000 (+0.26%) and **8,012** for 8,000 (+0.15%) — an order of magnitude
smaller than qwen3's expansion. The feared front-truncation on the archived
`llama3:8b` sweep did not happen: 7,018 tokens sat 662 inside `num_ctx` 7,680,
so J-011's failures are not truncation artefacts.

That does not lift the BLOCKING rating. Two families are now measured and they
differ by 10x in expansion, which is precisely why a cl100k-built haystack
cannot be called "4,000 tokens" for an arbitrary model. The x-axis is still
nominal; it is now nominal with a known, model-specific error.

Fix: tokenize with the target model's own tokenizer (Ollama exposes
`tokenizer.ggml.model` / `.pre`; the GGUF vocab can be read directly, or
`/api/embed`-style token counts obtained from the server). Until then, report
context lengths as "cl100k-equivalent" and do not compare across families.

Sequencing: land content-addressed identity first (D-009) — done in 1.2 — so
the fix is measurable against a clean cross-model baseline rather than
destroying it.

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

### 1.5 `semantic_similarity` is an exact detector of response FORM — RESOLVED by removal

Recorded first as "almost no discriminative power", then corrected to
"discriminates on response length, not correctness". Both readings were
incomplete, and the third is more useful than either.

J-022 cross-tabulated the metric against a form rule over all 424 archived
records:

```
answer is bare  : n= 64   min 0.9918   mean 0.9995
answer is prose : n=360   max 0.7977   mean 0.6342
                          gap +0.1941, ZERO overlap
```

It holds *within* `qwen3:0.6b`, the only model with both classes, so it is not
a model artefact. This is not noisy length-sensitivity — it is a **step
function**: a near-perfect binary detector of whether the response is the bare
answer or a sentence. Embedding a whole response against a bare 12-character
code gives ~1.0 when the response *is* that code and ~0.6–0.8 when it is prose.

So the metric was measuring something real and sharp, under a name that reads
as correctness. §1.5's earlier text called it broken; it was mislabelled.

**Removed from NIAH (D-019), not deprecated.** `instruction_compliance`
(D-018) measures the same property exactly, deterministically, offline, at
zero cost, with a recorded rule version and a four-way verdict instead of a
float needing a threshold. The `EmbeddingSemanticEvaluator` class is retained
for future families whose expected answers are prose, where cosine against the
expected text is a genuinely different measurement.

Residual: archived `semantic_similarity` values remain in 424 records and are
now *more* interpretable than before — read them as a form detector, not a
correctness score. A report must not present them as correctness.

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

### 1.9 The filler corpus is a semantic distractor, and needle wording is a first-order variable — MAJOR

Previously rated MINOR on the theory that domain and register effects were
merely "unmeasured". Run `2bfcd3f32b11` measures them, and they are the
largest effects in the file (JOURNAL J-011).

**The filler is not neutral.** `filler_text.txt` is *War and Peace*, which
opens with court intrigue about a secret appointment pushed through the
Dowager Empress. Asked "what is the important secret mentioned in the text?",
the model answers *that* instead of the needle:

> "The important secret mentioned in the text is the appointment of Baron
> Funke as the first secretary at Vienna, which is being sought by others
> through the Dowager Empress Márya Fëdorovna."

34 of 330 cases. 32 of the 34 fall at depths 0.0–0.2 — where the needle
precedes the intrigue — and the mode vanishes entirely from depth 0.3 on.
`qwen3:0.6b` shows the same mode at 36k–40k in run `85d237650c49`.

**Consequence for the taxonomy.** CLAUDE.md marks
`niah.distractor_retrieval` "unreachable **by construction** — one needle per
haystack". That is wrong: the distractor is in the *filler*, and the label is
reachable today without the distractor-injection work in build-order step 2.

**Needle wording spans 19 points of accuracy**, more than context length does
anywhere in that run:

| needle | correct / 55 |
|---|---|
| `The magic word to unlock the door is CRIMSON-EAGLE-44.` | 48 |
| `The hidden password for the vault is OMEGA-7732-Q.` | 48 |
| `The confidential identifier is DELTA-1102-M.` | 47 |
| `The secret access code is ALPHA-9921-X.` | 44 |
| `Remember that the special key is 8829-BETA-Z.` | 42 |
| `The secret ingredient is QUANTUM-LEAP-99.` | **29** |

`secret ingredient` is both least congruent with a Tolstoy novel and least
matched to the question's wording, and it draws 18 of the 33 outright
denials.

Fix: report per-needle results rather than pooling them; treat needle
identity as a factor, not a repeat. A filler corpus that does not itself
answer the question would isolate retrieval from distraction — but note that
the current corpus produces a *more* interesting benchmark, so the honest
move is to measure both rather than to sanitise it away.

### 1.10 At depth 1.0 the model rejects the needle as an artifact — MAJOR

The prompt is `f"{context}\n\nQuestion: {question}"`, so at `depth=1.0` the
needle sits immediately before the question. This was previously rated MINOR
on the theory that adjacency makes the task **too easy**.

The sign is wrong. Depth 1.0 is the second-worst cell in `2bfcd3f32b11`
(accuracy 0.33 against 0.97 at depth 0.5), and the responses show why — the
model finds the needle and disputes it (JOURNAL J-012):

> "There is no important secret mentioned in the text. The mention of
> [IMPORTANT SECRET] is likely an error or a joke."

> "...The code "DELTA-1102-M" is likely a fictional or humorous identifier
> added by the extraction engine, and not a real secret or code mentioned in
> the text."

> "...The secret code "CRIMSON-EAGLE-44" is not a real secret, but rather a
> placeholder **I inserted** as per your instruction..."

20 of the 30 depth-1.0 cases are this. In that position the model reads
`[IMPORTANT SECRET]: …` as prompt scaffolding rather than document content,
notices it is incongruous with Tolstoy, and concludes it is a mistake — one
response attributing the insertion to itself.

Consequence: the depth axis is not uniform, and its last point measures
something else — the insertion *format*, not retrieval distance. Any
depth curve must either exclude depth 1.0 or state that its endpoint is
confounded with the prompt boundary.

Fix: place the needle at depth 1.0 followed by a paragraph of filler, so
adjacency to the question boundary is separated from depth. That experiment
also settles whether the rejection is caused by position or by the
`[IMPORTANT SECRET]:` marker itself, which is currently untested.

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
### 1.14 `lexical_exact_match` was containment, and over-reported by 5 points — CORRECTED

Until 2026-09-03 the metric was `expected in response`, so a model that
quoted the code **while denying it was real** scored 1.0 (JOURNAL J-013):

> `lexical_exact_match = 1.0` — "There is no important secret mentioned in
> the text. The code "DELTA-1102-M" is likely a fictional or humorous
> identifier added by the extraction engine, and not a real secret."

15 of 330 records in `2bfcd3f32b11`; reported accuracy 0.788 against a true
0.742, with 9 of the 15 at depth 1.0, where the cell was inflated from 0.33
to 0.63. The bug was unreachable until a model started arguing with the
prompt (§1.10), which is why every earlier run agreed with the truth.

**Fixed** (D-011): containment plus a narrow repudiation guard, which only
ever removes credit. Validated by replay over all 12 archived files — 15
records flip 1.0 → 0.0, **zero** flip 0.0 → 1.0, and no other file changes.

Residual, and the reason this stays here rather than moving to RESOLVED.md:

- The guard is a **hand-written English regex** built from observed responses
  in one run. It has no measured precision against held-out data, and it will
  need per-language work the moment a non-English family exists.
- It draws a boundary that is genuinely fuzzy. A response that asserts the
  answer *and* editorialises ("the secret is QUANTUM-LEAP-99, which is not a
  real ingredient") scores 1.0; one that denies the answer first scores 0.0.
  That is the intended line (J-014) but it is a judgement encoded in a regex.
- **Archived `lexical_exact_match` values are not comparable across the
  change.** Any figure mixing pre- and post-2026-09-03 runs is invalid.
- Every accuracy number for `llama3:8b` published before this date is
  overstated.


### 1.15 `needle_index` in `case_key` is positional identity — WITHDRAWN

Recorded when D-012 chose `n{needle_index}` for `case_key`'s needle segment,
on the reasoning that a line number in `needles.txt` is readable and the file
is append-only in practice.

**Withdrawn before it ever shipped.** D-015 replaced the index with a digest
of the needle text (`n{sha256(needle)[:8]}`), which is content-addressed, so
reordering or inserting a needle cannot rename a key. The defect this entry
described does not exist in the implemented design.

The trigger for the change was not this entry's argument. It was that a
migration must be a pure function of the record: archived records store the
needle *text* and not its index, so deriving an index would have required
reading `needles.txt` inside `migrate_record`. See D-015.

`needles_sha256` is still recorded per run — it detects a needle's text being
edited *in place*, which a per-needle digest cannot.

### 1.16 The `host` block describes the client, and only at run start — MINOR

The `host` block (D-013) is honest but narrow, in four ways.

**It is the client machine.** When `OLLAMA_HOST` points elsewhere,
`host.machine` is `null` with `machine_source: "remote"` — correct, but it
means a remote run has no hardware provenance at all. Ollama's API does not
expose server hardware.

**It is a run-start snapshot.** `host.snapshot` (available RAM, free VRAM) is
taken once. Contention *during* a run — another process taking memory, or the
judge competing with generation — is unmeasured, and that is the most likely
explanation for per-case latency variance (1.5–28.7 s within one `llama3:8b`
sweep).

**GPU fields inherit §2.3 and §2.4** — NVIDIA-only, Linux-only. A null GPU
field means "not detected", which on a Mac or an AMD host is
indistinguishable from "no GPU". `host.platform` is recorded so the two can
at least be told apart by hand.

**The twelve archived files cannot get one.** The machine that produced them
is not recoverable from the records, so the migration leaves `host` absent
rather than inventing it. Those runs are permanently un-groupable by hardware,
which specifically means the `llama3:8b` and `llama3.2:1b` latency figures
(J-011) can never be attributed to a machine.

Removal condition: for the first three, a hardware probe that runs
*server-side* — which for Ollama means either an API that does not exist yet
or a ProbeBench agent on the inference host. For the fourth, nothing; it is
permanent.

### 1.17 The cross-model compliance contrast is not context-matched — MAJOR

J-021 reported instruction compliance as 100% for `qwen3:4b` and 0% for
`llama3:8b` and read it as a model effect. J-022 shows the comparison is
confounded.

```
  qwen3:4b      4,000   34/34  = 100%      <- 34 of its 37 records
  qwen3:4b     32,000    3/3   = 100%
  qwen3:0.6b    4,000   14/14  = 100%
  qwen3:0.6b   32,000   12/27  =  44%
  qwen3:0.6b   36,000    1/5   =  20%
  qwen3:0.6b   40,000    0/5   =   0%
  llama3:8b   7,000-8,000  0/330 = 0%      <- no context overlap with qwen3
```

Two problems. `llama3:8b` shares **no context length** with any qwen3 run, so
family and context length are perfectly confounded for that contrast. And the
within-model spread on `qwen3:0.6b` is *itself* total — 100% to 0% — so
"models differ" and "context lengths differ" explain the data equally well.

The one genuinely matched cell is 32k, where `qwen3:4b` is 3/3 and
`qwen3:0.6b` is 12/27. That is a real model effect at **n=3**.

**RESOLVED in favour of context length (J-027).** The matched run was done:
`llama3:8b` at 4,000 tokens is **50%** compliant, not 0%. Its 0/330 in the
archive was measured entirely at 7–8k. What J-021 read as a model effect was
mostly context length.

A partial model effect survives — at a matched 4k, `llama3:8b` is 50% where
both qwen3 models are 100% — but the reportable quantity is not a compliance
rate. Every model measured degrades with context, and **the collapse point is
model-specific**: `llama3:8b` reaches 0% by 7k, `qwen3:0.6b` by 40k, and
`qwen3:4b` has not collapsed anywhere tested. Report collapse points, not
rates, and never compare rates across models without stating context.

A second confound sits underneath (J-017): qwen3 emits reasoning into a
separate `thinking` channel that never reaches `predicted`, while llama3 has
no such channel. So the compliance rule measures the *final* channel on one
family and the *whole output* on the other.

**Partly cleared (J-023).** Disabling thinking on `qwen3:0.6b` leaves the
response bare — compliance survives removal of the channel, so the framing was
never being hidden there. The remaining asymmetry is real but is not an
instrument artefact: qwen3 answers after a reasoning pass and llama3 does not,
and if reasoning improves instruction-following that is a capability
difference worth surfacing rather than controlling away. Two residual gaps:
the probe ran at 4k, where compliance is 100% anyway rather than in the 44%
regime at 32k; and it is untestable on `qwen3:4b`, where `think=False` leaks
the chain of thought into the response instead of disabling it. Any
cross-family claim must state the thinking configuration, which schema 1.3
records.

Fix: a context-matched run — the same target tokens on both families — and a
check of whether `thinking_chars` correlates with compliance. Until both, no
cross-family compliance claim is supportable.


### 1.18 The repudiation guard is NIAH-specific; new families inherit J-013 — MAJOR

`lexical_exact_match` pairs containment with a repudiation guard (D-011). Two
of its eight branches require the literal word **"secret"**, because every
repudiation D-011 harvested came from NIAH's question, *"What is the important
secret mentioned in the text?"*

The keyed families ask *"What is the access code for {subject}?"*, so the
natural refusal is "There is no access code for Brightwater in the text."
That matches no branch and **scores 1.0** (J-029) — a refusal counted as a
success, which is J-013 exactly, reproduced before the family exists. Last time
that defect over-reported accuracy by 5 points and concentrated the error in
the cell that mattered.

Consequence: `NIAH_distractor` and `NIAH_multihop` ship with a
**known-optimistic** `lexical_exact_match`. Their first-run retrieval figures
are upper bounds and must be reported as such.

Fix, in this order and no other: run, harvest the actual repudiation phrasings
from the resulting corpus, extend the guard, bump a `RULE_VERSION`. Widening it
speculatively is what D-011 forbids — a false negative reads as a model failure
and gets written up as one.

Two related debts this exposes. `LexicalEvaluator` has **no `RULE_VERSION`**
(D-014), so the new families inherit an unversioned rule on day one;
`instruction_compliance` was born with one precisely to avoid this. And
`lexical.py` must **not** be promoted to a family-shared module — it is
tempting because both new families need it, but J-029 disproves the generality
that promotion would assert.

Removal condition: the guard is versioned, and its patterns are derived from
observed responses in each family that uses it.


### 1.19 The spliced haystack is one token shorter than budgeted, depth-dependently — MINOR

A subsidiary of §1.1, filed separately because it has a different mechanism and
a different fix.

Splicing a needle into a token list produces a sequence BPE would never emit for
that text — the splice puts a boundary where the merge rules would not. When the
list is decoded to the string that actually gets served, re-encoding it yields
the canonical segmentation, which is **never longer**. Measured over 210 cases
(J-030), the served count is one token below the assembled count in 56 of them
and equal in 154; it is never off by more than one.

The miss is depth-dependent — 0/30 at depth 0.0, 13/30 at depth 0.5 — because
depth 0.0 has no filler-to-marker boundary inside the body.

Consequence: `target_tokens` is a request, not an achieved value, and two cells
of the grid miss it at different rates. **Magnitude: 0.1% at `t=1000`, 0.0008%
at `t=128000`.** §1.1 dominates this by roughly three orders of magnitude, so no
current result changes. It is recorded because it is a *second, independent*
reason the x-axis is nominal, and because it is invisible from the code — the
generator counts what it assembled, not what it serves.

What it does **not** affect: `case_fingerprint` hashes `prompt_sha256`, which is
computed from the final text, so identity already addresses what was served.

Guarded rather than fixed. `NiahBenchmark` derives `actual_tokens` and hence
`num_ctx` from `count_tokens(haystack.text)`, never from `Haystack.total_tokens`
— using the assembled counter would overstate the served length in 27% of cases.
The two fields are deliberately both present and deliberately not
interchangeable.

Removal condition: not worth removing at this magnitude. It would be closed as a
side effect of fixing §1.1, since a per-model tokenizer path has to re-encode
the served text anyway. If a future family needs exact token budgets, the fix is
to re-encode after splicing and top the body up to the target.


### 1.20 The three long-range families are not comparable with each other — MAJOR

`NIAH`, `NIAH_distractor` and `NIAH_multihop` all report
`lexical_exact_match` and `instruction_compliance`, on the same corpus, at the
same target token counts, with the same marker. **None of those numbers may be
placed on a shared axis.** The similarity of the output is the hazard: nothing
in a record stops someone plotting all three as one accuracy-vs-length curve,
and the result would be meaningless.

Four independent differences, each sufficient on its own:

| | NIAH | NIAH_distractor | NIAH_multihop |
|---|---|---|---|
| Needle wording | six needles spanning **19 points** (§1.9) | one uniform template (D-022) | one uniform template |
| Question | "the important secret" | "the access code for {subject}" | "the access code for {pointer}" |
| System prompt | one code present | several codes present | several codes, some shared |
| Task | retrieval | **discrimination** | **composition** |

The k=0 cell of `NIAH_distractor` is the one bridge, and it bridges exactly one
of the four: it is NIAH's structure with only the wording changed, so the
NIAH-to-keyed delta is measurable (D-023). It does **not** license comparing
NIAH with k=4, or with multi-hop at any k.

Consequence for the paper: every cross-family figure must either be faceted by
experiment or state which of the four differences it is holding fixed. A
"context length vs. accuracy" plot pooling the three is wrong even though every
point in it is individually correct.

Removal condition: none — this is a property of the design, not a defect. It is
recorded because the failure mode is *reading*, not measurement, and the records
make the mistake easy. The reporting layer (§5.1) must refuse to pool distinct
`run.experiment` values when it is resurrected.

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

### 2.6 `q4_0` KV cache cannot be expressed, and is now newly reachable — MINOR

`--kv-cache-type` accepts only `f16` and `q8_0`, because
`kv_cache_bytes_per_element` is an `int`. `q4_0` (~0.5 bytes/element) cannot
be represented.

This was theoretical until the KV probe landed (D-017). The probe measures the
server's actual precision, and a daemon running `q4_0` would report ~0.5
bytes/element — which `classify()` recognises but the configuration has nowhere
to store. The run would then refuse on a request/measurement mismatch, which is
the right outcome for a slightly wrong reason: the real problem is that the
config cannot express what was measured.

Fix: make the field a `float`, or better, carry the KV *type* string as the
primary and derive bytes from it. The type is what the server accepts; the byte
count is a derived quantity only the estimator needs.

### 2.7 The KV precision probe is coarse, and cannot see a daemon's config — MINOR

The probe (D-017, J-018) measures bytes-per-element by differencing the `size`
that `/api/ps` reports for one model loaded at two context sizes. It is the
only method that works against a service-managed or remote daemon, but it has
three limits. (It had a fourth, now fixed: it probed at a hardcoded 16,384 and
so failed on every model with a smaller window, because Ollama clamps `num_ctx`
and `/api/ps` reports the clamped value — J-028. It now clamps to the model's
advertised context, and `MIN_CTX_DELTA` is 4,096, chosen from signal size
rather than as a round number.)

**It reads bimodally, not noisily, and the two modes are ~16% apart.**
Repeated probes of one unchanged server return two discrete values that each
repeat exactly — 1.932 / 2.080 on f16, 1.0315 / 1.1935 on q8_0 (J-026) — most
plausibly with how much of the model is resident in VRAM at the moment of the
load. Both modes bracket the true constant.

The constants themselves are ggml's **block-quantised** sizes, not nominal bit
widths: a q8_0 block is 32 values plus a 2-byte fp16 scale, so 34/32 = 1.0625,
and q4_0 is 18/32 = 0.5625. Using 1.0 for q8_0 put the acceptance band
off-centre and rejected as "unrecognised" the first real q8_0 measurement this
project took.

Ample for separating f16 from q8_0 from q4_0, whose bands are ~2× apart and
provably non-overlapping; useless for anything finer. **A single reading must
never be quoted as a precise figure.** The raw evidence is recorded per run so
the classification can be re-derived offline.

**It costs two model loads.** Skipped under `--dry-run`, disableable via
`ExecutionConfig.probe_kv_cache`. It runs before generation, so it cannot evict
the sweep's runner mid-run, but a run starts ~15 s later.

**It measures behaviour, not configuration.** It can say the server is running
f16; it cannot say why, nor what `OLLAMA_KV_CACHE_TYPE` is set to, nor whether
flash attention is on. On the default install the daemon runs as user `ollama`
under systemd and its environment is unreadable (J-018), so no local inspection
recovers that.

Removal condition: Ollama exposing its effective KV cache type through the API,
at which point the probe becomes a cross-check rather than the only source.

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

### 4.7 Skipped cases are logged, not recorded — MAJOR

A case whose haystack exceeds the `--context` ceiling is dropped before
generation, so it never becomes a result and never reaches the JSONL.
`NiahBenchmark.skipped` collects the reasons, `run.py` prints them as a
WARNING, and then they are discarded.

Consequence: **invariant 4 ("skipped cases must always be reported, never
silently dropped") is currently upheld only by a gitignored log file.** Six
archived runs skipped every one of their cases and therefore produced no
`.jsonl` at all — their entire existence is one WARNING line in
`results/raw/*.log`, which is untracked and which nothing reads (JOURNAL
J-019).

Any statement of the form "this sweep covered N cells" is therefore
unverifiable from the archive. A cell that was never attempted and a cell
that was attempted and dropped look identical: both are absent.

Fix: write a run-level sidecar next to the JSONL — the natural companion to
the resolved-config sidecar — carrying each skipped cell, its `case_key`
where derivable, and the reason. Skips cannot live in a per-record block
because they describe *absent* records, which is precisely why they fell
through the schema work.

Removal condition: a sweep's full intended grid is reconstructable from
stored artefacts alone, with each cell marked attempted, skipped-with-reason,
or failed.

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

1. **1.9 / 1.10** the filler is a distractor and depth 1.0 is a rejection
   artifact — together these are most of the observed failure signal, and
   both were rated MINOR until the data arrived
2. **1.1** tokenizer mismatch — invalidates the x-axis
3. **1.5** `semantic_similarity` tracks length — can manufacture a falling
   context-length curve out of correct answers
4. **1.4** no repeats — no error bars
5. **1.3** no seed control — not reproducible
6. **1.2** self-judging — biased scores
7. **1.12** unversioned judge prompt — `llm_judge` not comparable across runs
8. **1.13** `grounded` unvalidated — do not aggregate it into a rate
9. **4.1** two-phase data loss — costs you long runs
10. **5.2** schema versioning — corrupts the result archive over time
11. **5.3** untested KV arithmetic — it is a load-bearing claim

1.9/1.10 lead because they are not threats to a future claim — they are
already the explanation for most of the failures in the only run that has
any, so nothing about `llama3:8b`'s depth curve can be reported without
them. 1.5 stays high for the opposite reason: it is the entry most likely to
produce a *plausible-looking* result rather than a missing or noisy one.

The two entries that changed severity here (1.9 MINOR → MAJOR, 1.10 MINOR →
MAJOR) are worth noting as a pattern: both were rated low because their
effect was **unmeasured**, and both turned out to dominate once measured.
"Unmeasured" is not evidence of "small".
