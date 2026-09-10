# ProbeBench

A controlled evaluation framework for **diagnosing** LLM failures, not just
scoring them.

## How to deliver changes (propose, don't apply)

This section applies when the repo's git identity is **SumeetBhosale17
<sumeetbhosale1947@gmail.com>** (check with `git config user.email`; the
remote is `git@github.com:SumeetBhosale17/probebench.git`). It overrides the
default "just make the edit" behaviour.

**Default mode: propose.** Do not use Edit/Write on tracked files. Deliver
the change as code *in your reply*, so it can be read, understood, and
applied deliberately. The purpose is comprehension and change tracking — a
silently applied diff teaches nothing and is easy to lose track of.

**Permission to write is explicit and single-use.** Only when the request
contains an explicit instruction — "write", "apply", "edit the file",
"commit", "go ahead and change it", "implement it in the repo" — may you
modify files, and only for that specific request. Permission does not carry
over to the next turn or to files outside what was asked for. If it is
ambiguous, propose.

**Always allowed without asking** (these do not mutate tracked files):

- Reading and searching: `cat`, `sed -n`, `grep`, `find`, Read, Explore.
- Running things: `uv run pytest`, `uv run ruff check src/`, `uv run pyright`,
  `uv run probebench ... --dry-run`, `./scripts/smoke_test.sh`.
- Scratch work in the session scratchpad directory.

### `docs/` is written, never proposed

**Everything under `docs/` is yours to write directly with Edit/Write.** The
propose-don't-apply rule above covers `src/`, `tests/`, and config; it does
**not** cover documentation. Do not hand back prose for the user to paste in
by hand — write it, then say in your reply which files you touched and what
changed.

The reason the propose rule exists is comprehension: a silently applied code
diff teaches nothing. That does not transfer to docs. Documentation is the
*output* of the comprehension, not a thing to be comprehended by retyping,
and routing it through a copy-paste round trip is pure friction — which is
how DESIGN.md and LIMITATIONS.md drift out of date while the code moves.

This applies to all seven:

- **`docs/JOURNAL.md`** — append-only, newest last. Invariant 12: write the
  entry *before* the fix, because the fix destroys the evidence. Never
  rewrite or delete an existing entry; correct one by appending a new entry
  that references it.
- **`docs/DECISIONS.md`** — append-only. Invariant 13: when a choice is made
  between live options, record it *before* the change lands, because the
  implementation destroys the alternatives. `Status: open` with options and
  no decision is a valid, expected entry — that is how an analysed but
  unmade choice is recorded without making it.
- **`docs/LIMITATIONS.md`** — add a new limitation when you find one, with a
  severity and a removal condition. **Correct an existing entry when
  evidence contradicts it** — a limitation whose stated diagnosis is now
  known to be wrong is worse than no entry, because it is trusted.
- **`docs/RESOLVED.md`** — when a limitation's stated removal condition is
  met, write its entry here and strike it from LIMITATIONS.md. The two moves
  are one move: a limitation that quietly disappears is indistinguishable
  from one that was forgotten. See "Resolving a limitation" below.
- **`docs/DESIGN.md`** — update the what/how/why for any subsystem whose
  architecture you change.
- **`docs/articles/`** — one file per piece, drafted proactively as findings
  reach a state worth writing about. See "Writing about it" under Research
  process for the trigger and the shape. `docs/articles/README.md` carries the
  written/queued index and the four-beat template.
- **`docs/CODEMAP.md`** — what every file does and why. Update it when a file
  is added, removed, or changes purpose; a codemap that lists a file which no
  longer exists is worse than none.
- **`CLAUDE.md`** — keep the status table, invariants, and highest-priority
  list in sync with reality when a change moves them.

Two things this permission does **not** license. Do not use a docs edit to
smuggle in a decision the user has not made — record the options and mark it
open, as LIMITATIONS §1.5 and DECISIONS D-006 do. And do not delete a
limitation because you believe it is fixed; a limitation is removed when its
stated removal condition is met, and the entry says so.

### The failure loop

When anything fails — a traceback, a saturated number, a metric that will not
move, a result that contradicts an earlier one — the sequence is fixed, and
every step has a document. **Do not skip to step 4.**

| # | Step | Ask | Lands in |
|---|---|---|---|
| 1 | **Record** | What happened, verbatim? What was expected? | JOURNAL, *before* touching anything (inv. 12) |
| 2 | **Diagnose** | Why did it happen — mechanism, not symptom? What earlier choice made it reachable? | JOURNAL `Mechanism` / `Validated` |
| 3 | **Decide** | What are the options? What does each one cost, and what does each change about *what is measured*? | DECISIONS, *before* the change lands (inv. 13) |
| 4 | **Fix** | — | code, per the propose rule above |
| 5 | **Verify** | What validation would fail if this regressed? What did we actually get versus what we predicted? | RESOLVED + DECISIONS `What we got` |
| 6 | **Bound** | What does this *not* cover? | LIMITATIONS (new/corrected) + RESOLVED `Residual` |

Three failure modes this ordering exists to prevent, all of which have already
happened in this repo:

- **Fixing before recording** destroys the evidence. The KV formula (J-001)
  survived only because `attempted to allocate 36000.00 MB` was still on
  screen when the arithmetic was checked against it.
- **Diagnosing from a confounded control.** J-006 changed the judge *model*
  while the prompt stayed broken, concluded "capacity floor", and was wrong;
  J-009 held the model fixed, changed only the prompt, and inverted the
  conclusion. Step 2 is not finished until one variable moved.
- **Deciding silently.** Once the code is written, the rejected option stops
  being a weighed alternative and becomes a thing nobody thought of — so it
  gets proposed again. Step 3 is what makes "we already tried that, here is
  why not, and here is what would change our mind" answerable in one grep.

Steps 3 and 5 are the two that get skipped, and they are the two a research
project cannot skip: **step 3 is why we did it, step 5 is what it got us.**
Neither is recoverable after the fact — a reconstructed rationale is written
knowing the outcome, so it cannot be trusted to remember the option that was
considered and dropped early. DECISIONS D-001–D-005 and D-007–D-010 are
marked *reconstructed* for exactly this reason.

### Resolving a limitation

A fix is not finished when the code lands. Write the
[docs/RESOLVED.md](docs/RESOLVED.md) entry, which carries six parts:

**The limitation** (raw evidence), **Methodology** (how it was investigated
— *including the steps that were wrong*), **Decision** (what was chosen and
what was rejected, with reasons), **Why it works** (the mechanism, not "it
stopped happening"), **How we know** (validation that would fail if the fix
regressed), **Residual** (what it does not cover).

Three conditions gate an entry. The mechanism is understood, not just the
symptom suppressed; validation exists that would catch a regression; the
residual is stated. **A fix that works for reasons you cannot explain is a
JOURNAL entry (`Mechanism: unknown`), not a RESOLVED one.**

Two parts are load-bearing and get skipped first, so guard them. *Decision*
must record what was **rejected** — the alternative that looks obvious in
hindsight is exactly what someone will propose again. *Methodology* must
record wrong turns; R-003 reached the wrong conclusion first from a
confounded control, and that is the most reusable thing in the entry.

If the choice was recorded in DECISIONS.md when it was made — which invariant
13 requires — *Decision* is a pointer to that entry (`see D-00n`) plus only
what was learned since, and the D entry's `What we got` is filled in at the
same time. Two copies of one argument drift; the D entry is the copy that
records what was believed *before* the outcome was known, so it is the one
that keeps its value.

Scope: an entry resolves what it actually resolves. R-003 fixed the judge's
scoring contract and explicitly did **not** resolve §1.2 (self-judging),
which stays open. Partial credit stated plainly beats a limitation struck
early.

### Shape of a proposal

Every code proposal carries these five parts. Skipping any of them is what
makes a proposal useless to apply.

1. **Where it goes.** Target file as a clickable path, plus an anchor —
   function/class name, or the exact existing lines it sits after or replaces.
   e.g. "in [src/probebench/core/result.py](src/probebench/core/result.py),
   inside `to_record()`, after the `response` block".
2. **The code, complete.** A fenced block containing exactly what gets typed.
   No `...`, no "and so on", no summarised bodies. If a function changes, show
   the whole function, not the changed lines alone. Unchanged surrounding
   lines may be trimmed as long as the anchor in (1) makes placement
   unambiguous.
3. **Why.** What it does and why this way — matching the "comments explain
   why" convention. Name any non-obvious decision explicitly.
4. **What it touches.** Any invariant from "Non-negotiable invariants" that
   the change interacts with, and whether it changes *what is measured*
   (schema, prompts, case construction, metric semantics) or only how it runs.
   If it changes what is measured, say so in bold — that is a paper-validity
   concern, not an implementation detail.
5. **How to verify.** The exact commands to run afterwards, and what a pass
   looks like. Include the schema/migration test when `to_record()` changes
   (invariant 7).

### Multi-file changes

Give numbered steps in dependency order — the order they can actually be
applied in, each step leaving the tree working (or, if it cannot, say which
steps are only valid as a set). One code block per file per step, each with
its own anchor. Do not merge unrelated files into one block.

Say up front which files the whole change touches, so the scope is visible
before reading any code.

### What not to do

- Do not shrink a change to make it fit a reply. If it is 200 lines, give
  200 lines. Truncating for brevity defeats the point.
- Do not describe code in prose in place of writing it ("you'd add a field
  here for the fingerprint"). Prose is the explanation, not the deliverable.
- Do not apply "while I was in there" fixes, even when write permission was
  given for something else. Propose them separately.
- Do not propose a `docs/` change as pasteable prose. Write it — see
  "`docs/` is written, never proposed" above.
- Do not stage or commit anything unless explicitly asked (this restates
  the harness default, which holds here too).

## What this project is for

Most benchmarks answer "how well did the model do?" ProbeBench is being built
to answer harder questions:

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

The paper is the primary deliverable. Blog posts and articles are a
secondary, derived output — the same JOURNAL/DECISIONS material written for a
broader audience — and exist to make the work legible while it is still in
progress, not to replace or race ahead of the paper. See "Writing about it"
under Research process.

## Status: built vs. planned

Read this table before believing anything else in this file. The four
questions above are the *goal*; three of them are not yet answerable from a
ProbeBench result file.

| Capability | Status | Where |
|---|---|---|
| Case generation over a (length × depth) grid | **built** | `benchmarks/long_range_dependency/NIAH/` |
| Three scalar metrics per case | **built** | `evaluation/long_range_dependency/NIAH/` |
| Memory feasibility model (KV arithmetic, `plan`) | **built** | `core/preflight.py` |
| Failure isolation, retries, health checks | **built** | `core/{runner,retry,health}.py` |
| Two-phase execution, judge context pinning | **built** | `core/runner.py`, `evaluation/.../judge/` |
| Structured provenance per case | **built** | `core/result.py` |
| Schema migration path | **built** | `core/migrations.py` — 1.0→…→1.6, **shape first, version second** (J-033). J-005's three-shapes debt is now paid: 658 records migrate to one shape |
| Multi-block haystack primitive | **built** | `benchmarks/long_range_dependency/haystack.py` — k blocks at k depths, full inventory; single-needle path byte-identical (166 fingerprints replay) |
| Needle inventory in the record | **built** | schema 1.5 — `needle_inventory`, `realised_depth`, `filler_tokens_used`. This is what makes the rule tier affordable |
| Shared experiment pipeline | **built** | `experiments/pipeline.py` (D-021) — the KV-probe/preflight/two-phase ordering exists once |
| `NIAH_distractor` (keyed discrimination) | **built, unrun** | k ∈ {0,1,2,4,8} decoys (D-022, D-023); k=0 is the calibration cell |
| `NIAH_multihop` (two-hop composition) | **built, first run done** | Produced the project's first deliberate failures (J-031, J-032). Registry rotation added (D-024) — rank and subject identity are now separable |
| Case identity (`case_key`, `case_fingerprint`) | **built** | `core/case_identity.py`, plus one `identity.py` per family (D-012, D-015) |
| Hardware provenance per run | **built** | `core/hostinfo.py` (D-013); null when Ollama is remote |
| KV precision measured, not assumed | **built** | `core/kvprobe.py` (D-017); a mismatched run refuses to start |
| Layered config (`probebench.toml`) | **built** | `core/settings.py` (D-016); measured/operational split is a type error |
| `grounded` label on the judge | **built, unvalidated** | `evaluation/.../judge/` (D-010); LIMITATIONS §1.13 |
| **Error taxonomy** (labels, not scores) | **planned** | `core/taxonomy.py` |
| **Failure classification** (rules + LLM tier) | **planned** | `core/classification.py`, `classification/` |
| **Cross-model joins** (content-addressed case identity) | **planned** | `core/case.py`, `reporting/load.py` |
| **Structured failure records** in the schema | **planned** | `core/result.py`, `core/migrations.py` |
| Cross-run load / join / aggregate | **built** | `reporting/load.py` — migrate + flatten + join, with §1.20 / J-021 / §1.2 as **raises** |
| Aggregation / reporting across runs | **partly wired** | `load.py` is live; `markdown.py`, `csv.py`, `json.py` still dead (§5.1) |

**What ProbeBench is today, stated honestly: a scorer with unusually good
plumbing, plus a genuinely novel memory-feasibility model.** It emits three
floats per case — `lexical_exact_match`, `semantic_similarity`, `llm_judge` —
and, since D-010, exactly one categorical field: `grounded`, which fired on
**1 of 44** archived records. That is a first probe of the label tier, not the
taxonomy; nothing else says *how* a response was wrong.

**Do not close this gap by adding a fourth metric.** The missing layer is
categorical, not scalar. `grounded` is deliberately kept out of `metrics` for
this reason — `metrics` is `dict[str, float]`, and a boolean in there becomes
an averageable rate that destroys what the label carries. See "Target
architecture" below.

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

The taxonomy follows the same rule: a family-agnostic core in `core/`,
family-specific subtypes under `classification/<family>/<EXPERIMENT>/`.

## Read these first

- **[docs/DESIGN.md](docs/DESIGN.md)** — the two production failures that
  shaped the architecture, root-cause analysis with the arithmetic, and
  what/how/why for each subsystem. Read before changing execution flow,
  memory handling, or the judge.
- **[docs/LIMITATIONS.md](docs/LIMITATIONS.md)** — every known limitation,
  graded BLOCKING / MAJOR / MINOR. Read before making any claim about
  results.
- **[docs/JOURNAL.md](docs/JOURNAL.md)** — the running record of what was
  observed, when, and what it meant. Read to find out what has already been
  tried and what is still unexplained.
- **[docs/DECISIONS.md](docs/DECISIONS.md)** — every choice made between live
  options: what was rejected, why, what would reopen it, and what the choice
  actually got us versus what it promised. Read before re-proposing anything;
  it is the cheapest document to check and the one most likely to already
  contain the answer.
- **[docs/RESOLVED.md](docs/RESOLVED.md)** — limitations that are actually
  fixed, with the methodology, the rejected alternatives, and why each fix is
  correct rather than merely effective. Read before re-proposing an approach
  that was already considered and rejected.
- **[docs/CODEMAP.md](docs/CODEMAP.md)** — what every file does, how, and why
  it exists. The "why" column is the point: a file's relevance is usually a
  limitation it closes or an invariant it enforces, which is invisible from
  the code. Read first when you do not know where something lives.

When you discover a new limitation, add it to LIMITATIONS.md with its
severity and what would be needed to remove it. When you resolve one, move it
to RESOLVED.md with the reasoning. When you choose between options, record it
in DECISIONS.md **before** the change lands. When you change architecture,
update DESIGN.md's what/how/why for that subsystem. When something surprising
happens, write a JOURNAL.md entry **before** you fix it — see "The failure
loop" above for the full sequence, and "Research process" below for why.

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
   see LIMITATIONS §5.2, and JOURNAL J-005, which finds the violation is
   wider than §5.2 records.)

The next five follow from the diagnostic work. They are stated now so the
architecture is built against them rather than retrofitted.

8. **A failed or skipped classifier leaves the classification block ABSENT,
   with `decided_by: "none"` — never `OK`.** This is invariant 1 applied to
   labels: unclassified is missing data, not a pass. Synthesising `OK` for
   an unclassified case would corrupt the very dataset the classifier is
   measured against.

9. **Rules before models.** Anything decidable by rule is decided by rule.
   The LLM tier only ever sees the residual the rules could not resolve, and
   its labels are recorded as `decided_by: "llm"` so they can be excluded
   from any analysis that must be reproducible. A rule is free and
   deterministic; an LLM classifier is neither.

10. **The taxonomy is a closed, versioned set.** Adding, renaming, or
    removing a label bumps `TAXONOMY_VERSION`. A classifier that emits a
    label outside the set raises — an unknown label is an error, never a new
    label.

11. **Case identity is content-addressed.** Anything that changes the
    model's input changes `case_fingerprint`. Never join results across
    construction changes on grid coordinates alone — `case_id` today is
    sweep-dependent and unsound for this (JOURNAL J-004).

12. **Write the journal entry before the fix.** The fix usually destroys the
    evidence.

13. **Write the decision entry before the change lands**, whenever a choice
    was made between live options and it changes what is measured, responds
    to a JOURNAL or LIMITATIONS entry, fixes a sequencing, or is a deliberate
    refusal to act. The implementation destroys the alternatives: once the
    code exists, the rejected option reads as one nobody thought of. A
    rejection is not recorded without its `Revisit if:` condition — a
    rejection made under constraints that no longer hold is a zombie, and
    binds work it should not.

## Target architecture (PLANNED)

None of this section is implemented. It is recorded here so that work moves
toward it instead of accreting more metrics.

### Error taxonomy — `core/taxonomy.py`

A closed, versioned label set. A **family-agnostic core** any benchmark
family can emit, plus namespaced **family subtypes** that each declare a
parent, so analysis can roll up across families without knowing any family.

Core labels, in precedence order — the first that applies becomes
`primary_label`:

| Label | Meaning | Decided by |
|---|---|---|
| `GENERATION_ERROR` | No response exists; the provider call failed | rule |
| `EMPTY_OUTPUT` | Empty or whitespace-only response | rule |
| `TRUNCATED` | Output cut off by the token budget | rule |
| `REFUSAL` | Model declined to answer | LLM |
| `CONTEXT_ECHO` | Reproduced input context instead of answering | rule |
| `NON_ANSWER` | On-topic, never commits to an answer | LLM |
| `INSTRUCTION_IGNORED` | Answered a different question than asked | LLM |
| `WRONG_ANSWER` | Committed to a specific answer; it is wrong | rule |
| `FORMAT_VIOLATION` | Content correct, output contract violated | rule |
| `OK` | Satisfies the task | rule |

`OK` is a label, not the absence of one. Every classified case carries
exactly one `primary_label`, so "no label" means "not classified" and
nothing else (invariant 8).

NIAH subtypes:

| Label | Parent | Meaning | Reachable today |
|---|---|---|---|
| `niah.distractor_retrieval` | `WRONG_ANSWER` | Returned a different needle from the same haystack | **yes** — 7/16 multi-hop failures (J-032); also reachable via filler competition (§1.9) |
| `niah.fabricated_value` | `WRONG_ANSWER` | Code-shaped string absent from the whole prompt | yes |
| `niah.partial_value` | `WRONG_ANSWER` | Near-miss of the expected code | yes |
| `niah.wrong_section` | `WRONG_ANSWER` | Quoted a different region of the haystack | yes |
| `niah.needle_verbatim_echo` | `FORMAT_VIOLATION` | Echoed the needle sentence instead of the code | yes |

**Corrected 2026-09-09.** This section used to say
`niah.distractor_retrieval` was unreachable by construction, because
`create_haystack` inserted exactly one needle. It was wrong twice over, and both
corrections are instructive.

First, §1.9 found the label reachable *without any code change*: the distractor
is in the **filler**. *War and Peace*'s opening court intrigue was returned
instead of the needle in 34 of 330 cases, 32 of them at depths 0.0–0.2. A
"single-needle" haystack has a competing answer in it whether or not we planted
one.

Second, the haystack builder now plants k blocks, so the label is reachable by
construction too — and it **fires**: 7 of 16 multi-hop failures return a planted
but wrong code (J-032). Note the order in which we learned that. At n=6 the label
fired 0 times and we wrote down that real failures did not look like this; fifty
cases overturned it the same day.

The lesson worth keeping is not about this label. It is that "unreachable by
construction" is a claim about the construction, and it goes stale the moment the
construction changes — so it belongs next to the enum, dated, rather than in
someone's head.

### Classification — `core/classification.py`, `classification/<family>/<EXPT>/`

Two tiers, rules first (invariant 9).

**Tier 1, rules.** Deterministic, free, offline, always runs. Decides
`GENERATION_ERROR`, `EMPTY_OUTPUT`, `TRUNCATED` (from Ollama's
`done_reason`), `OK` (exact and normalised-modulo-whitespace), and the whole
`WRONG_ANSWER` subtree. Confidence is `1.0` by construction.

The reason so much is rule-decidable: **we constructed the haystack, so we
know exactly what is in it.** Distinguishing a fabricated value from a
distractor from a wrong section is a substring search over the prompt against
a known needle inventory, not a judgement call. Synthetic benchmarks should
exploit this rather than reach for a model.

**Tier 2, LLM.** Sees only what rules could not decide — `REFUSAL` vs.
`NON_ANSWER` vs. `INSTRUCTION_IGNORED`, which are genuinely semantic.
Returns a label from the closed set, a confidence, and a reason.

**No second model call.** The judge call is already the expensive one on a
memory-bound host, and a second per-case call would reintroduce exactly the
runner pressure invariant 3 exists to prevent. The existing judge prompt
gains a `label` field: `{"score", "label", "reason"}`. The score continues to
flow to `metrics`; the label flows to the classification block. A missing or
out-of-set label invalidates the *label* only — the score still records.

`classification/` is a new top-level package parallel to `evaluation/`,
deliberately not inside it: an `Evaluator` returns
`EvaluationResult(name, score: float, metadata)`, and forcing labels through
a float-shaped interface is the exact failure mode this pivot exists to
avoid.

**The rule tier must be replayable over stored JSONL**, not only live. Rules
will be iterated on, and re-running them must never require re-running the
models. This constrains the record: it has to carry enough evidence to
re-derive a judgement offline.

### Case identity — for cross-model joins

Answering "do different models fail on the same inputs?" requires a case to
be identifiable independently of which model ran it. `case_id` today is
`niah_{target}_{depth}_{counter:04d}` where the counter runs over the whole
sweep, so it shifts when `--needles` or `--depths` change or when a cell is
skipped, and the needle is not in it at all. It is already inconsistent
across our own archived runs (JOURNAL J-004).

Two keys, because they answer different questions:

- **`case_key`** — the grid coordinate:
  `niah/t{target_tokens}/d{depth:.2f}/n{needle_index}`. Sweep-independent,
  no counter.
- **`case_fingerprint`** — the content address: a hash over everything
  determining the model's input (experiment, `prompt_sha256`, system prompt,
  expected answer, needle, target tokens, depth, tokenizer provider+name).
  Store `prompt_sha256`, never the prompt — a 128k-token haystack per case
  would make the archive unusable, and the hash still detects filler-corpus
  drift.

**The tension with LIMITATIONS §1.1, worked through.** §1.1 (BLOCKING) is
that haystacks are built with cl100k for every model, so reported context
lengths are nominal. But that same choice makes cases byte-identical across
models, which is what a clean join needs. Fixing §1.1 makes prompts differ
per model, and `case_fingerprint` stops joining across them.

That is not a conflict to resolve — it is the truth surfacing, and the two
keys absorb it. `case_fingerprint` asserts *identical input* (strict
comparability; holds today, and correctly stops holding after the §1.1 fix,
because the inputs genuinely become different). `case_key` asserts *same
design point* (survives the fix, but then means "same nominal cell", not
"same input"). **A cross-model claim must state which join it used.**

Sequencing consequence: **land content-addressed identity before fixing
§1.1.** Doing so while cl100k-for-all still holds gives a verified-clean
cross-model baseline, which turns "how much of the cross-model difference was
tokenization?" from an assumption into a measurement. Fixing §1.1 first
throws that baseline away.

### Structured failure records — `core/result.py`

`to_record()` gains a `classification` block: `taxonomy_version`,
`primary_label`, `labels` (a list — a response can be both `TRUNCATED` and
`FORMAT_VIOLATION`), `decided_by`, `classifier` and `classifier_version`,
`confidence`, `rules_fired`, `evidence` (which distractor came back, what the
model said instead, whether the emitted value appears in the prompt at all),
and `error`.

Also added: `case.case_key`, `case.case_fingerprint`, `case.prompt_sha256`;
and `response.done_reason` / `eval_count` / `prompt_eval_count`, which
`models/ollama.py` currently discards — `TRUNCATED` is free to detect and
undetectable today.

Per invariant 7 this bumps `CURRENT_SCHEMA_VERSION` and registers migrations.
Note the archive currently has **three** record shapes all declaring `"1.0"`
(J-005), so migrations must detect shape by field presence, not by declared
version. Archived records cannot receive real fingerprints — the prompt was
never stored and cannot be reconstructed — so `null` is the honest value and
those files join on `case_key` only.

## Before the taxonomy can be validated

**Corrected 2026-09-07 (J-022).** This section used to say the benchmark had
no discriminating power. That is false, and what falsifies it was in the
archive the whole time.

**Retrieval** is still near-saturated on qwen3 NIAH runs, and J-003 stands **for
NIAH**: no genuine NIAH retrieval failure has been isolated from an instrument
artefact.

**It does not stand for multi-hop.** A 50-case `NIAH_multihop` sweep on
`qwen3:0.6b` at **4,000 tokens** — the length at which every NIAH metric in the
archive is 1.0 — failed **16 times** (J-031, J-032). Two separable modes:

```
 9  no code emitted          ("None of the access codes listed in the text
                               relate to Redmont.")
 7  returned a planted code  — but the wrong one
```

The dominant mechanism is that the model resolves the pointer's *subject* and
not its *referent*: it reports that the pointed-from location has no code and
never takes the second hop. A composition failure, not a retrieval failure. Every
classification came from a substring search over the stored `needle_inventory` —
no judge, no second model call.

**The 2×2 is no longer degenerate.** Five of those 50 are bare-and-wrong — the
cell J-022 found empty across 424 NIAH records, and the one that makes
`instruction_compliance` independent of `lexical_exact_match` rather than a proxy
for it.

The largest effect in the run was not predicted: **which registry entry the
pointer names.** Rank 2 fails 80% at both k=4 and k=8, at document depths 0.685
and 0.314 — rank, not position. It is confounded with subject identity by
construction, and separating them is the next run.

**Instruction-following is not.** `instruction_compliance` (D-018) fires on
360 of 424 archived responses, and on `qwen3:0.6b` it produces the project's
first graded degradation curve: **100% → 44% → 20% → 0%** across
4k → 32k → 36k → 40k. It also separates models — `qwen3:4b` obeys 37/37,
`llama3:8b` obeys 0/330 — though that contrast is not context-matched and is
`Validated: not yet` (§1.17).

The one non-scalar exception proves the point rather than weakening it. The
`grounded` label (D-010) fired on exactly **1 of 44** archived records
(J-010), and 41 of those 44 predictions are bare code strings with nothing to
be ungrounded about. That is three informative records and one positive — it
shows the instrument works on the case it was built for and says nothing
about how often it is right (LIMITATIONS §1.13).

A taxonomy of failure modes cannot be validated against a dataset with no
failures. Classifier precision and recall are undefined, label reachability
is unknown, and a rule that never fires is indistinguishable from a rule that
is correct. **Produce failures first, derive the taxonomy from what they
actually look like, then build the classifier.** The labels above are a
hypothesis to test against a failure corpus, not a specification to implement
against.

These must all hold before any claim that the taxonomy works:

- A corpus with a non-trivial failure rate — target ≥50 failing cases
  spanning ≥3 distinct failure modes. **16 of 50, spanning 2 modes, as of
  J-032** — the first real progress on this line, all of it from
  `NIAH_multihop` at 4k.
- Hand-labelled ground truth on a sample (n ≈ 100), so per-label precision
  and recall are measurable. Someone has to read 100 responses.
- Rule-tier vs. LLM-tier disagreement rate reported; ideally a second human
  on a subsample.
- A reachability audit: every label either observed at least once, or
  documented as unreachable and why.

## Build order

1. ~~**Identity and evidence capture.**~~ **DONE**, including
   `reporting/load.py`. 658 records across six declared versions now load as one
   table. Building it immediately surfaced J-033: the migration chain normalised
   the *version* and not the *shape*, so three shapes were declaring `"1.6"` and
   24 records had `model` as a bare string. CLAUDE.md predicted this — "the first
   real consumer of `core/migrations.py` is what forces §5.2 to be repaid
   properly rather than declared fixed" — and it was right, including the
   mechanism.

2. **Make failures exist.** ~~Push contexts toward the feasibility ceiling;
   finer depth grid; a weaker model.~~ **Largely done, and the ordering in this
   step was wrong.** Length and model size were listed first and neither is what
   produced failures. Changing the task's *structure* did: `NIAH_multihop` fails
   16 of 50 at **4,000 tokens**, the shortest length in the grid, on a model
   whose NIAH scores are all 1.0 there (J-032).

   ⚠️ **This changes what is measured.** Three families now emit identical
   metric names over identical corpora and are **not comparable** with each
   other (§1.20) — flag it in results and in the paper. `NIAH_distractor` is
   built but **unrun**; its k=0 cell is the calibration everything cross-arm
   depends on (D-023).

   *Correction:* this step used to claim distractor injection was "the only
   route by which `niah.distractor_retrieval` becomes reachable at all". §1.9
   disproved that before any code changed — the distractor is in the filler,
   and *War and Peace* was returned instead of the needle 34 times.

3. **Freeze the taxonomy** from the observed inventory, at
   `TAXONOMY_VERSION = "1.0"`.

4. **Rule classifier**, developed offline against the stored corpus — no live
   model calls, which is what makes iteration affordable.

5. **LLM classifier** for the residual only; extend the judge's JSON
   contract.

6. **Cross-model join.** Two or more models over a fingerprint-identical
   corpus; report the label agreement/disagreement matrix. This is the first
   output a scorer structurally cannot produce.

7. **Resurrect the reporting layer** (LIMITATIONS §5.1) as the consumer of
   all of the above.

## Research process

**This project's most valuable result so far was not planned.** The memory
work started as a crash — a 36 GB KV cache allocation on a 14 GB machine —
became a root-cause analysis, then a predictive model validated against the
observed failure, then a CLI command. It is arguably the most novel thing in
the repo. Nothing about that sequence was on a roadmap.

So the process of discovery is recorded, not just the outcomes. The
observation half goes in JOURNAL.md; the deliberation half goes in
DECISIONS.md. See "The failure loop" above for how the two interleave.

**Where.** [docs/JOURNAL.md](docs/JOURNAL.md), append-only, newest last. One
file, no tooling, no template to fetch.

**Entry format** — an ID, a date, a title, and six lines:

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

**Trigger — write the entry before the fix.** When any of these happen, open
JOURNAL.md *first*: an unexpected crash or traceback; a number that is
anomalous, saturated, or will not move; a discrepancy between advertised and
measured behaviour; a fix that works but you cannot explain. Paste the raw
error and the exact command that produced it, then fix.

The reason is concrete. The KV cache formula was only derivable because the
raw `attempted to allocate 36000.00 MB` figure survived long enough to be
checked against `2 · 36 · 8 · 128 · 2 · 256000`. A fix applied first would
have destroyed that number, and the predictive model with it.

**Graduation.** An entry explaining a mechanism graduates into DESIGN.md's
what/how/why. One that threatens a claim graduates into LIMITATIONS.md with a
severity and a removal condition. One that is a result becomes paper
material. The entry keeps its ID and gains a marker
(`Status: graduated → DESIGN §3.1`). **Entries are never deleted or
rewritten** — they record what we believed at the time, which is the part
that makes the process worth anything.

**Keep it cheap.** Incomplete entries are committable. "Mechanism: unknown"
is a valid entry; recording the observation is the point, explaining it is a
later job. A process that is too expensive to follow does not get followed.

### Recording the deliberation

**Where.** [docs/DECISIONS.md](docs/DECISIONS.md), append-only. Same
discipline, applied to choices rather than observations:

```markdown
## D-00n — <title>
Status: open | accepted | executed → R-00n | superseded by D-00m | reversed
Decided: <date or "not yet"> | Trigger: <J-00n, §x.y, or none> | Changes what is measured: yes/no

**The problem.**  What forced a choice. Link the evidence; do not restate it.
**Options.**      Each one, with what it gives, what it costs, and what it
                  changes about what is measured.
**Decision.**     What was chosen, and the reason that actually decided it.
**Rejected.**     Each rejected option, why, and `Revisit if:` what reopens it.
**Predicted.**    What we expect this to get us. Falsifiable where possible.
**What we got.**  Filled in after the change lands. "not yet" until then.
```

`Predicted` / `What we got` is JOURNAL's `Expected` / `Observed` applied to a
choice, and it is the field the file exists for. An entry whose `What we got`
contradicts its `Predicted` is the most useful entry in the file — D-005 is
one: the prompt fix worked, and the reason it worked (prompt quality beat
model size) was not what the original diagnosis predicted.

**Not every choice is a decision.** Two live options, and at least one of:
it changes what is measured; it answers a JOURNAL or LIMITATIONS entry; it
fixes an ordering; it is a refusal to act; someone will propose the rejected
option again. "Used `pathlib` over `os.path`" is a preference, not a
decision.

**Boundary with RESOLVED.md.** A D entry is written *forward* — it may be
open, unvalidated, or never implemented, and it holds the options while the
choice is live. An R entry is written *backward* and requires validation.
When a D entry's change lands and its removal condition is met, the R entry's
**Decision** section becomes a pointer (`see D-00n`) plus what was learned
since. Do not maintain two copies of the same argument.

### Writing about it — blogs and articles

Alongside the paper, this project writes for a broader audience as it goes —
LinkedIn-shaped articles and blog posts, not just an eventual paper's
methods section. The first was on the KV cache incident: what the crash
looked like, what caused it, how the KV cache formula above is derived, and
how the KV cache's size changes with precision — f16 at 2 bytes/element,
`q8_0` at roughly 1, `q4_0` at roughly 0.5, all against the same
`kv_bytes_per_token` identity. That is the template: an incident, its
mechanism, the arithmetic that proves the mechanism, and a generalisable
lesson — not a results announcement.

**Draft proactively, do not wait to be asked.** When a JOURNAL entry
graduates to `Disposition: publishable`, when an R-00n lands in RESOLVED.md,
or when a D-00n's `What we got` is filled in with a real result, that is the
trigger to draft an article and say so — the same way a limitation or a
decision gets written up without being asked for. J-002's runner-thrash
diagnosis, J-009's self-correction of a confounded control, and D-010's
groundedness label are all shaped like the KV cache piece: a concrete
failure, a mechanism, evidence that would fail if the explanation were
wrong.

**Where.** `docs/articles/<slug>.md`, one file per piece, written directly —
these are ordinary docs writes, not proposals. Draft the whole piece, not an
outline to be expanded on request.

**What a draft is not.** Publishing. Writing the file is a docs edit;
posting it anywhere external is a visible, hard-to-reverse action on your
account, and gets proposed and confirmed like any other — never assume the
draft is authorised to go out because it was authorised to be written.

**Do not outrun the evidence.** An article is only as reliable as the
JOURNAL/DECISIONS/LIMITATIONS material it is drawn from at the moment it is
written. J-003 stands — no retrieval failure has been observed yet — so an
article claiming to have found model failures would be false regardless of
how well it reads. Draft what the record actually supports; if a finding is
still open (a D entry with `What we got: not yet`, a JOURNAL entry with
`Status: open`), the article says so rather than rounding up to a
conclusion.

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
    taxonomy.py        # (planned) FailureLabel, TAXONOMY_VERSION, subtypes
    classification.py  # (planned) Classification, Classifier, ClassifierChain
  benchmarks/<family>/haystack.py  # k-block splice primitive + inventory
  benchmarks/<family>/<EXPT>/      # case generation (NIAH, NIAH_distractor,
                                   #   NIAH_multihop)
  evaluation/<family>/<EXPT>/      # evaluators (lexical, semantic, judge)
  classification/<family>/<EXPT>/  # (planned) family rule sets
  experiments/pipeline.py          # the generic run: probe -> cases -> plan ->
                                   #   generate -> evaluate -> write (D-021)
  experiments/registry.py          # ExperimentSpec registry — add new here
  experiments/<family>/<EXPT>/run.py  # orchestration
  models/        # Ollama client, registry, installer, host resolution
  reporting/     # jsonl (wired); markdown/csv/json (dead code);
                 #   load.py (planned) — migrate + join across runs
```

## Commands

```bash
uv run probebench <model>                    # run all experiments
uv run probebench doctor [model]             # environment check
uv run probebench plan <model>               # what contexts fit this machine
uv run probebench <model> --dry-run          # cases + memory plan, no calls
uv run probebench models inspect <model>     # geometry, GQA ratio, KV cache ladder
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
- **Diagnose, don't score.** When tempted to add a metric, ask whether the
  question is really "how much?" or "what kind?" If it is the second, it
  belongs in the taxonomy.

## Current highest-priority issues

Reordered around the pivot. Items 1–3 come before the tokenizer fix because
each is either a precondition for it being measurable or a precondition for
having anything to diagnose.

1. **Run the rotated multi-hop grid (D-024).** The rotation axis is built and
   the Latin square is verified, but it has **never been run**. It answers the
   biggest open question in the only real failure corpus: is the 80%-at-rank-2
   effect positional, or is it about Kingsley? Until it runs, every reading of
   J-032's rank paragraph is one of three.

   Then a second model, then hand-label a sample. Target is ≥50 failing cases
   spanning ≥3 modes; the current corpus has 16 spanning 2.

2. **Run `NIAH_distractor` at all, starting with k=0.** It is built and has
   never been executed. The k=0 cell is D-023's calibration — until it runs,
   the keyed-vs-legacy wording delta is an assumption, and every cross-arm
   figure in both new families depends on it.

3. **The repudiation guard is blind to the new families (§1.18, J-029).** Both
   keyed families ship a **known-optimistic** `lexical_exact_match`. J-031's two
   refusals happened to score 0.0 because they quote no code — a refusal that
   *quotes* one would score 1.0. Harvest phrasings from the corpus item 1
   produces, then extend the guard and version it.

4. **Tokenizer mismatch (LIMITATIONS §1.1, BLOCKING).** Haystacks are built
   with `tiktoken cl100k_base` but served to models with different
   tokenizers, so "4,000 tokens" is nominal and differs per model family.
   This invalidates the x-axis of every context-length curve and blocks
   cross-model length claims. Fix *after* item 2, so the change is
   measurable against a clean baseline.

5. **No repeats (§1.4)** — `--needles 1` means one Bernoulli sample per grid
   cell, so no error bars are possible.

6. **No seed control (§1.3)** — runs are not reproducible.

7. **Self-judging (§1.2)** — the judge defaults to the generation model.

8. **Two-phase data loss (§4.1)** — nothing is written to disk until
   generation finishes; a crash loses the whole run. `--single-phase` is
   safer for long runs until checkpointing lands.

9. **Reporting layer is dead code (§5.1)** — `markdown.py`, `csv.py`,
   `json.py` are never called.
