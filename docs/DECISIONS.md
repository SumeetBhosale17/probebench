# ProbeBench — Decision Record

What we chose, **what we chose against**, and what it actually got us.

Companion documents: [JOURNAL.md](JOURNAL.md) (what we observed),
[LIMITATIONS.md](LIMITATIONS.md) (what is still wrong),
[RESOLVED.md](RESOLVED.md) (fixes that are verified),
[DESIGN.md](DESIGN.md) (how the system works now).

---

## Why this file exists

The other four documents record observations, threats, verified fixes, and
mechanism. None of them records a **choice at the moment it is made**, and
three kinds of reasoning fall through the gap.

**Decisions taken before anything is resolved.** RESOLVED.md is gated: an
entry needs the mechanism understood, validation that would catch a
regression, and a stated residual. That gate is correct and should not be
loosened — but it means a decision has nowhere to live between "we understand
the failure" and "the fix is proven". J-007 offers three options for
`semantic_similarity` (drop it, redefine it as a per-sentence max, rename it).
Whichever is picked, the reasoning would not appear anywhere until the change
is validated, which may be months.

**Decisions with no failure attached.** "Land content-addressed identity
*before* fixing the tokenizer mismatch" is a real decision with real
reasoning, and it currently lives in CLAUDE.md prose. CLAUDE.md is
instructions, kept in sync with reality — so the day that decision is
executed, the argument for it gets edited away. The same is true of "the
label tier makes no second model call" and "`classification/` is not inside
`evaluation/`".

**What a choice was predicted to buy, versus what it bought.** RESOLVED.md's
*How we know* validates that a fix is **correct**. It does not ask whether the
option delivered what was claimed for it. Those are different questions, and
only the second one accumulates into a finding about method.

The test for whether this file is earning its place: a year from now, someone
proposes coercing an out-of-range judge score to `1.0`. The answer should be
findable in one grep, with the reason it was rejected and the condition under
which that rejection would be revisited — without reading four documents to
reconstruct it.

## When to write an entry

Write one when a choice is made **between at least two live options** and at
least one of these holds:

- it changes **what is measured** — schema, prompts, case construction,
  metric semantics, the taxonomy;
- it is a response to a JOURNAL entry or a LIMITATIONS entry;
- it fixes an ordering or a sequencing (do X before Y, and Y is now blocked);
- it is a deliberate **refusal to act** — "we are not fixing this yet, and
  here is why" is a decision and the most commonly lost one;
- someone will plausibly propose the rejected option again.

Do **not** write one for a choice with no live alternative. "Used `pathlib`
instead of `os.path`" is not a decision, it is a preference.

### The forcing rule: record the decision before the change lands

Invariant 12 says write the journal entry before the fix, because the fix
destroys the evidence. This is its companion: **a decision that changes what
is measured is recorded before it is implemented**, because implementation
destroys the alternatives. Once the code is written, the rejected option stops
being a live possibility that was weighed and becomes a thing nobody thought
of — which is exactly how it gets proposed again.

An entry may be written with `Status: open` and no decision at all. That is
the correct state for a choice that has been analysed but not made, and it is
what stops analysis being redone from scratch. It is also the mechanism by
which CLAUDE.md's rule — *do not use a docs edit to smuggle in a decision the
user has not made* — is satisfied: lay out the options, mark it open, choose
later.

## Entry format

An ID, a title, two header lines, and six fields:

```markdown
## D-00n — <title>
Status: open | accepted | executed → R-00n | superseded by D-00m | reversed
Decided: <date or "not yet"> | Trigger: <J-00n, §x.y, or none> | Changes what is measured: yes/no

**The problem.**  What forced a choice. Link the evidence; do not restate it.
**Options.**      Each one, with its consequence — what it gives, what it costs,
                  and what it changes about what is measured.
**Decision.**     What was chosen, and the reason that actually decided it
                  (not every reason that supports it).
**Rejected.**     Each rejected option, why, and `Revisit if:` the condition
                  that would reopen it.
**Predicted.**    What we expect this to get us. Falsifiable where possible.
**What we got.**  Filled in after the change lands. `not yet` until then.
                  This field is the point of the file.
```

`Predicted` / `What we got` is the same discipline JOURNAL applies to
observations (`Expected` / `Observed`), applied to choices. An entry whose
`What we got` contradicts its `Predicted` is not an embarrassment — it is the
most useful entry in the file, and it stays.

## Relationship to the other documents

| Event | Where it goes |
|---|---|
| Something surprising happened | JOURNAL.md, **before** the fix (invariant 12) |
| It threatens a claim | LIMITATIONS.md, severity + removal condition |
| A choice is made between options | **here**, **before** the change lands (invariant 13) |
| The removal condition is met | RESOLVED.md, citing the D-id |
| The system's behaviour changed | DESIGN.md what/how/why |

**The boundary with RESOLVED.md, stated precisely, because these two will
otherwise drift into two copies of the same argument.** A D entry is written
*forward*: it may be open, unvalidated, or never implemented, and its job is
to hold the options while the choice is live. An R entry is written
*backward*: it requires validation, and its job is to show a fix is correct.

When a D entry's change lands and its limitation's removal condition is met,
the R entry's **Decision** section becomes a pointer — "see D-00n" — plus only
what was learned *since*. Do not re-argue the options there. Conversely, an R
entry never replaces a D entry: R-001 proves the memory preflight is correct;
D-001 is where "why not catch the allocation error and retry smaller?" is
answered.

### Rules

1. **Append-only.** Entries are never deleted or rewritten, for the same
   reason JOURNAL entries are not: they record what we believed with the
   information we had. A decision that turns out wrong is `Status: reversed`
   with a new entry explaining why, not an edit.
2. **`Rejected` is load-bearing and gets skipped first.** An entry with no
   rejected option is either not a decision or is hiding the alternative that
   will be proposed again next month.
3. **`Revisit if` is mandatory on every rejection.** It is the same device as
   LIMITATIONS' removal condition, and it exists to prevent zombie decisions
   — a rejection made under constraints that no longer hold.
4. **Cheap entries are committable.** `Status: open` with options and no
   decision beats no entry. `What we got: not yet` is expected on any entry
   younger than the change it describes.

---

# Entries

Entries D-001 to D-005 and D-007 to D-010 were **recorded retrospectively on
2026-08-31**, reconstructed from RESOLVED.md, the invariants and target
architecture in CLAUDE.md, and the code. D-006 is the first entry written
while its choice was still open. Their reasoning is real and was applied at the time; the
*deliberation* was not written down when it happened, which is the practice
this file changes. Reconstructed entries are marked as such, because a
reconstruction is weaker evidence than a contemporaneous record — it is
written knowing the outcome, so it cannot be trusted to remember an option
that was considered and dropped early.

---

## D-001 — Predict memory feasibility rather than discovering it by crashing
Status: executed → R-001 | *reconstructed 2026-08-31*
Decided: 2025-08-19 | Trigger: J-001 | Changes what is measured: **yes** — it bounds which contexts are runnable at all

**The problem.** A 256,000-token context on a 14 GiB-free host killed the
Ollama runner (`attempted to allocate 36000.00 MB`) and took the whole run
with it. The guard that existed compared the request against the model's
advertised `context_length` and passed. See J-001, R-001.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Catch the 500 and retry at a smaller context | No new machinery; adapts to any host | Wastes a full model load per discovery; on a swapless host the failure is not always a clean exception; treats a closed-form quantity as a surprise |
| A fixed context ceiling per machine | Trivial; one constant | Wrong for every model — per-token KV cost varies by an order of magnitude with layer count, KV heads and cache precision |
| Compute the requirement ahead of the call and refuse infeasible cases | Predicts failures before they happen; the arithmetic is a *result*, not just a guard | Needs GGUF geometry extraction; is an approximation of total memory, not an allocation trace |

**Decision.** Compute it ahead of the call. What decided it was not
robustness but the exact match: `2 × 36 × 8 × 128 × 2 × 256,000` reproduces
the observed `36000.00 MB` **to the byte**. An arithmetic that reproduces a
real failure exactly is a predictive model, and a predictive model is
publishable in a way that a retry loop is not. The engineering choice and the
research choice pointed the same way.

**Rejected.** *Catch-and-retry* — discovering a computable quantity by
crashing. `Revisit if:` a backend appears whose memory cost is not derivable
from published metadata, in which case measurement is the only route.
*Fixed ceiling* — model-independent, therefore wrong per model. `Revisit if:`
never; it is dominated by the chosen option at every point.

**Predicted.** That the feasible context set becomes computable per (host,
model) pair before any model is loaded, and that the reference machine's real
ceiling is far below the advertised 262,144.

**What we got.** Both. `probebench plan` reports the feasible set; the
reference machine tops out near 88,800 tokens against an advertised 262,144
— a 2.9× gap that is itself a finding, and one that now bounds every
long-context claim the project can make. Unanticipated: the same arithmetic
became a CLI command (`models inspect`) and the most novel artefact in the
repo. Residual per R-001 — it models the KV cache, not compute buffers or
fragmentation (§2.1), and the arithmetic still has no unit test (§5.3).

---

## D-002 — Attack runner *identity*, not the 404
Status: executed → R-002 | *reconstructed 2026-08-31*
Decided: 2025-08-19 | Trigger: J-002 | Changes what is measured: no (timing only; see below)

**The problem.** A run died at case 3 with a 404 for a model that had
answered twice. The failure landed in the judge call. Ollama keys a
`llama-server` runner on `(model, num_ctx, …)`; generation passed a per-case
`num_ctx` and the judge passed none, so every case evicted and reloaded ~5 GB
twice. See J-002, R-002.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Retry the 404 | One-line change | 404 means "not resolvable in the manifest store" — retrying papers over a store that changed under the server, and can mask a genuinely removed model (§4.2) |
| Serialise into two phases so the models never coexist | Removes per-case interleaving; enables judge-side batching | Does **not** fix it — the judge still spawns a new runner per distinct generation `num_ctx` |
| Pin the judge's `num_ctx`, and bucket generation's to 512 | Collapses all judge calls onto one runner and all depths at one target size onto one | Forces judge-input truncation (a pinned window can be overflowed by an echoing response); over-allocates context (§1.8) |

**Decision.** Pin and bucket. What decided it was locating the *key*: the
churn was not caused by two models being large, it was caused by the harness
manufacturing new runner identities — including a one-token difference
(`16,511` vs `16,512`) spawning a separate server. Two-phase execution was
adopted as well, for different reasons (D-004), and explicitly **not** as the
fix for this.

**Rejected.** *Retrying the 404* — treats the symptom, and 404 is
semantically the wrong error to retry. `Revisit if:` the store-swap hypothesis
(§4.6) is confirmed and a retry can be made to distinguish it from a real
removal. *Serialisation alone* — insufficient, as above. `Revisit if:` never;
it was adopted alongside, not instead.

**Predicted.** Runner count per run drops to one judge runner plus one
generation runner per target size, and evaluation time falls once the judge
runner is resident.

**What we got.** Both, measured. A 25-case run went from 6 distinct runners to
5, with all depths at a size sharing one; judge evaluation went 5.7 s cold →
**1.7 s** warm. Also: a lesson that is now invariant 3, and the discovery that
*any* latency number from a single-phase run on a memory-constrained host is
measuring model loading, not inference. Unanticipated cost: the truncation
that pinning forces is still not recorded in `evaluation_details` (§1.11).
The 404's root cause remains unconfirmed (§4.6) — this decision removed the
pressure, not the cause, and R-002 says so.

---

## D-003 — A failed evaluator leaves its metric absent, never `0.0`
Status: executed (invariant 1) | *reconstructed 2026-08-31*
Decided: 2025-08 | Trigger: none — taken pre-emptively | Changes what is measured: **yes** — it defines what a missing measurement means

**The problem.** An evaluator can fail for reasons that have nothing to do
with the model under test: the judge times out, returns unparseable JSON, or
returns an out-of-range score. Something must be written to `metrics`.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Record `0.0` | Every case has every metric; denominators are constant; aggregation is trivial | **Silently biases every aggregate downward.** An infrastructure failure becomes indistinguishable from a model failure — the exact confusion this project exists to prevent |
| Record `null` inside `metrics` | Preserves the key; makes absence explicit | Every consumer must handle `None` in a float-typed dict; a careless `sum()` still coerces or crashes |
| Omit the key entirely | Missing data is missing; impossible to average by accident | Aggregation denominators vary per metric (§1.7); consumers must count what they averaged |

**Decision.** Omit the key. What decided it is that the two failure classes
must never merge: a judge that errored is *missing data*, and a model that
answered wrongly is a *result*. Any representation that lets the first be
averaged as the second is disqualified regardless of convenience.

**Rejected.** *`0.0`* — it is a lie about the model, and it is silent.
`Revisit if:` never. This is invariant 1. *`null` in the dict* — better, but a
key that exists invites arithmetic on it; omission makes the mistake
structurally impossible rather than merely discouraged. `Revisit if:` a
schema consumer needs a stable keyspace per record badly enough to outweigh
that, in which case the null must be typed and validated, not implicit.

**Predicted.** Aggregates over the archive are unbiased by evaluator
failures; consumers are forced to state their denominator.

**What we got.** Held under a real test: J-006's `100.0` left `llm_judge`
absent rather than recording a spurious `0.0` on a case whose response was
actually correct. Had `0.0` been recorded, R-003's prompt defect would have
looked like a model failure and probably gone unexamined. The predicted cost
also materialised — §1.7 is open, and no consumer reports its denominators
yet, because there is no consumer (§5.1). The generalisation of this decision
to labels is invariant 8, taken before any classifier exists.

---

## D-004 — Two-phase execution as the default, accepting the data-loss window
Status: executed | *reconstructed 2026-08-31*
Decided: 2025-08-19 | Trigger: J-002 | Changes what is measured: no (changes reported latency semantics)

**The problem.** Interleaving generation and judging per case thrashed the
runner on a memory-constrained host, and a failure in the judge destroyed the
completed generations that preceded it.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Single-phase (generate → judge, per case) | Each case's result is complete as soon as it is produced; nothing is held in memory | Per-case model swapping; a mid-run crash still loses the current case only |
| Two-phase (all generation, then all evaluation) | One judge load per run; clean separation of generation and evaluation timing | **Nothing reaches disk until phase 1 completes** — a crash in generation loses the entire run (§4.1) |
| Two-phase with checkpointing after each phase-1 case | Both benefits | Not built; needs a resumable on-disk intermediate |

**Decision.** Two-phase, with `--single-phase` retained as a flag. What
decided it: on a host where the two models cannot coexist, phase separation
is the difference between one judge load per run and one per case — and it
also makes evaluation timing interpretable, since a judge that is already
resident is being measured on inference rather than on loading.

**Rejected.** *Single-phase as default* — reintroduces the swap cost the
whole diagnosis was about. `Revisit if:` runs get long enough that §4.1's
data-loss window costs more than the swapping does; CLAUDE.md already advises
`--single-phase` for long runs, which is that condition being partly met
already. *Checkpointed two-phase* — not rejected on merit, only deferred; it
is strictly better and unbuilt. `Revisit if:` any run exceeds roughly an hour
of generation, at which point it stops being optional.

**Predicted.** One judge load per run; a failure in one case no longer
destroys others (with the failure-isolation change, invariant 5).

**What we got.** The judge-load reduction, measured (D-002). Failure
isolation held under J-006 — one case's judge raised and the run completed.
The predicted cost is live and unpaid: §4.1 is open and MAJOR, and the
deferred option is the fix. Recording it here means the deferral is a
decision with a trigger, not an oversight.

---

## D-005 — Fix the judge prompt; refuse to coerce the out-of-range score
Status: executed → R-003 | *reconstructed 2026-08-31*
Decided: 2026-08-31 | Trigger: J-006, J-009, §1.2 | Changes what is measured: **yes** — every archived `llm_judge` value predates it and is not comparable

**The problem.** The judge returned `100.0` (aborting one evaluation) and
graded two verbatim-correct responses `0.0` with self-refuting reasons. See
J-006, J-009, R-003.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Coerce `100.0 → 1.0` in the parser | One line; the run completes | Guesses at intent; converts a broken judge into a scoring one; **hides the prompt defect that caused it** — the next regression is quieter, not absent |
| Swap to a larger judge model | Worked in the observed control | The control was **confounded** (J-009): it changed the model while the prompt stayed broken. It shows a big judge tolerates a bad prompt |
| Remove the percentage detour from the prompt and strip the `(100%)` rubric twins | Removes the ambiguity at its source; costs nothing at inference | Invalidates every archived `llm_judge` value |
| Do all of the above | Belt and braces | The coercion would mask whether the prompt fix worked — the two are not independent |

**Decision.** Fix the prompt, add an explicit anti-verbosity clause, and
**deliberately do not coerce**. An out-of-range score is a judge *failure*,
and invariant 1 already prescribes the handling: leave the metric absent. The
deciding evidence was the un-confounded experiment J-009 finally ran — hold
the model at `qwen3:0.6b`, change only the prompt, and the same responses go
from `0.0` to `0.99`/`1.00` while a wrong code and a refusal still score
`0.0`.

**Rejected.** *Coercion* — the most tempting option and the one that would
have destroyed the finding. `Revisit if:` never for silent coercion; a
*logged, flagged* normalisation is a different proposal and would need its own
entry. *A bigger judge as the fix* — not rejected as a practice, rejected as
*this* diagnosis. `Revisit if:` a floor is ever located by an experiment that
holds the prompt fixed; J-009 shows it has not been.

**Predicted.** Judge scores become a property of the response rather than of
the judge's arithmetic, at both model sizes.

**What we got.** Confirmed by replay against the archived response strings at
both judge sizes, plus a live 3/3 run (R-003 *How we know*). Also got a
methodological result worth more than the fix: **judge-prompt quality
dominated judge-model size on this task**, which is a cheaper lever and a
direct warning for build-order step 5, where the same prompt gains a `label`
field. And a correction: J-006's stated mechanism was half wrong, from a
confounded control. That is why *Methodology* in RESOLVED.md must record wrong
turns. Residual: the judge prompt is still unversioned (§1.12), so nothing in
a record says which revision graded it.

---

## D-006 — What to do about `semantic_similarity`
Status: **open** — no decision made
Decided: not yet | Trigger: J-007, §1.5 | Changes what is measured: **yes**, under every option including doing nothing

**The problem.** `semantic_similarity` embeds the entire response and cosine-
compares it against a bare 12-character code, so it scores 1.000 for
`ALPHA-9921-X` and 0.649 for a fully correct answer that explains itself. It
ranks brevity, not correctness. NIAH degradation is expected to appear as
longer, hedgier answers — which this column would render as a falling curve
*even if every answer stayed correct*, producing a publication-shaped result
with no content. See J-007.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Drop the metric from NIAH | Removes a column that cannot be read as correctness | Loses the only continuous signal; `lexical_exact_match` and `llm_judge` are both effectively binary |
| Redefine as a max over response sentences | Measures "does any part of this response mean the expected answer"; keeps a continuous signal | Changes the metric's semantics — the archive is not comparable across the change; needs a sentence splitter, which is a new dependency and a new failure mode |
| Keep it, rename it to state what it measures | Cheapest; honest; nothing recomputed | A renamed misleading metric is still in the CLI summary table next to two correctness metrics; readers average what is in front of them |
| Keep it and stop printing it in the summary table | Preserves the archive; removes the misreading at the point of misreading | The column still exists in records and will be plotted by anyone who finds it |

**Decision.** None yet. This is recorded open deliberately: the analysis is
done, the choice is not, and the choice belongs to whoever is accountable for
the paper's claims. Note that the options are not independent of build order —
if the taxonomy lands first, the argument for keeping *any* continuous
similarity signal weakens, because "what kind of wrong" stops needing a float
to express it.

**Rejected.** Nothing yet. `Revisit if:` — the entry is the revisit.

**Predicted.** Under every option, the existing archive's
`semantic_similarity` column stops being comparable with future runs, or was
never meaningful to begin with. There is no option that preserves it.

**What we got.** not yet.

---

## D-007 — Diagnose with labels, not with a fourth metric
Status: accepted, not executed | *reconstructed 2026-08-31*
Decided: 2026-08-29 | Trigger: J-003, J-008 | Changes what is measured: **yes** — it adds a categorical output the schema does not have

**The problem.** ProbeBench emits three floats per case and nothing that says
*how* a response was wrong. J-008 is the case that makes this concrete: a
correct retrieval with a fabricated justification scores
`lexical_exact_match` 1.0, `llm_judge` 0.0 for the wrong reason, and
`semantic_similarity` 0.649 for a third wrong reason. Three numbers, none of
which says "the model invented a provenance".

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Add a fourth metric (e.g. a grounding score) | Fits the existing `EvaluationResult(name, score: float)` interface; no schema pivot | Compresses a *kind* into a magnitude. A grounding score of 0.4 does not say what was ungrounded, and the next failure mode needs a fifth float |
| Store the judge's free-text `reason` and analyse it later | Already available; zero new machinery | Not analysable at scale; not reproducible; two runs produce different prose for the same failure, so nothing can be counted |
| A closed, versioned label set with a rule tier and an LLM tier | Countable, joinable, reproducible for the rule tier; a rule that fires is free and deterministic | Real machinery: taxonomy, classifier chain, schema block, migrations. And it cannot be validated without a failure corpus, which does not exist (J-003) |

**Decision.** The closed label set. What decided it: **we construct the
haystack, so we know what is in it** — distinguishing a fabricated value from
a wrong section is a substring search against a known inventory, not a
judgement call. That makes most of the taxonomy rule-decidable, which is what
separates this from "add an LLM critic and hope". A synthetic benchmark should
exploit its own ground truth rather than reach for a model.

**Rejected.** *A fourth metric* — the failure mode this pivot exists to
avoid; it is also the option someone will propose again, because it is the
one that fits the existing interface. `Revisit if:` a genuinely continuous
quantity is needed (a *degree* of grounding rather than its presence), in
which case it is a metric **alongside** labels, never instead of them.
*Free-text reasons* — kept as evidence, rejected as the analysis unit.
`Revisit if:` never as the primary; it remains in `evidence`.

**Predicted.** A cross-model label agreement matrix — an output a scorer
structurally cannot produce. Also, that the taxonomy hypothesised in CLAUDE.md
will be **wrong in specifics** and must be frozen from an observed inventory
rather than implemented as specified.

**What we got.** The second half already, before any code: J-008 found a
failure mode — correct answer, fabricated grounding — that the hypothesised
core label set has no label for, and under which a rule classifier would
decide `OK`. That is one observed counterexample to the specification in the
first eight cases anyone read closely, which is the argument for build-order
step 3 (freeze *from* the inventory). The first half: not yet — it needs
steps 1, 2, and 6.

---

## D-008 — `classification/` is a top-level package, and the label tier makes no second model call
Status: accepted, not executed | *reconstructed 2026-08-31*
Decided: 2026-08-29 | Trigger: D-007 | Changes what is measured: no (structural)

**The problem.** Two placement questions follow from D-007. Where does
classification live relative to `evaluation/`, and how does the LLM tier get
its labels on a memory-bound host?

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Labels inside `evaluation/`, as another `Evaluator` | Reuses the runner's evaluator loop and registration | Forces a label through `EvaluationResult(name, score: float, metadata)` — a categorical output squeezed into a float-shaped interface, which is D-007's failure mode reappearing one layer down |
| `classification/` parallel to `evaluation/` | The return type can be a `Classification`; rules and evaluators evolve independently | A second package and a second chain in the runner |
| A second per-case model call for the LLM tier | Clean separation; the classifier prompt is independent of the judge prompt | Reintroduces exactly the per-case runner pressure invariant 3 exists to prevent; doubles the expensive call on the constrained host |
| Extend the judge's JSON contract to `{"score", "label", "reason"}` | No new call; label and score come from one grading pass | Couples them — a prompt change affects both, and J-009 shows the judge prompt is a *measured variable*, not a constant |

**Decision.** A parallel `classification/` package, and one extended judge
call. The coupling is accepted with a stated mitigation: a missing or
out-of-set label invalidates the **label only** — the score still records, per
invariant 1's logic applied twice in the same payload.

**Rejected.** *Labels as evaluators* — the float-shaped interface is the
thing being escaped. `Revisit if:` never; if it seems attractive, re-read
D-007. *A second model call* — rejected on host economics, not on design.
`Revisit if:` the project moves to a host where the judge model stays resident
with room to spare, at which point decoupling the prompts is worth the call
and this coupling should be reversed.

**Predicted.** The rule tier decides the large majority of cases offline and
replayably; the LLM tier sees only the genuinely semantic residual (`REFUSAL`
vs `NON_ANSWER` vs `INSTRUCTION_IGNORED`).

**What we got.** not yet — no classifier exists. The prediction is
falsifiable and should be checked directly once the rule tier runs over a
failure corpus: if the residual sent to the LLM tier is not a small minority,
this decision's economics do not hold and the coupling was not worth it.

---

## D-009 — Land content-addressed case identity before fixing the tokenizer mismatch
Status: accepted, not executed | *reconstructed 2026-08-31*
Decided: 2026-08-29 | Trigger: J-004, §1.1 | Changes what is measured: **yes** — both halves do, in opposite directions

**The problem.** Two changes are queued and they interact. §1.1 (BLOCKING) is
that haystacks are built with cl100k for every model, so reported context
lengths are nominal. J-004 is that `case_id` depends on sweep composition, so
there is no sound key to join runs on. Crucially, the *cause* of §1.1 —
one tokenizer for all models — is exactly what currently makes cases
byte-identical across models, which is what a clean cross-model join needs.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Fix §1.1 first (per-model tokenization) | Removes a BLOCKING validity threat sooner; the x-axis becomes real | Prompts become per-model, so no fingerprint-identical corpus ever existed under measurement. "How much of the cross-model difference was tokenization?" becomes permanently unanswerable |
| Fix identity first, then §1.1 | A verified-clean cross-model baseline is captured while cl100k-for-all still holds, turning that question into a measurement | §1.1 stays open longer, and every run archived meanwhile has a nominal x-axis |
| Do both at once | One migration | Two changes to what is measured land in one step with no baseline between them — the worst case for attributing any observed difference |

**Decision.** Identity first. The deciding argument is that the option
ordering is not symmetric: fixing §1.1 first **destroys** a measurement that
can never be recovered, while fixing identity first only *delays* a fix. When
one order is reversible and the other is not, the reversible one goes first.

The tension is absorbed by carrying two keys rather than resolved: `case_key`
(the grid coordinate — survives the §1.1 fix, but then means "same nominal
cell", not "same input") and `case_fingerprint` (the content address —
asserts identical input, holds today, and *correctly* stops holding after the
§1.1 fix, because the inputs genuinely become different). **Any cross-model
claim must state which join it used.**

**Rejected.** *§1.1 first* despite it being the more severe limitation.
`Revisit if:` the cross-model baseline is judged not worth capturing — i.e. if
the project abandons cross-model comparison, §1.1 should go first immediately.
*Both at once* — no baseline between two changes to what is measured.
`Revisit if:` never; this is the general rule, not a case-specific one.

**Predicted.** A fingerprint-identical multi-model corpus captured under
cl100k-for-all, against which the §1.1 fix's effect on measured performance
is quantifiable rather than assumed.

**What we got.** not yet — build-order step 1. Note the cost is already
accruing: every run archived before identity lands joins on `case_key` only,
and the archived files can never receive real fingerprints because the prompt
was never stored (`null` is the honest value).

---

## D-010 — Ship `grounded` as a label on the judge, ahead of the taxonomy
Status: accepted, executing
Decided: 2026-08-31 | Trigger: J-008, J-010, D-007 | Changes what is measured: **yes** — NIAH becomes retrieval *and* faithfulness

**The problem.** J-008 found a failure mode with no measure: a correct
retrieval carrying a fabricated justification. `lexical_exact_match` says 1.0,
`semantic_similarity` says 0.649 for the wrong reason, `llm_judge` said 0.0
for a third wrong reason. J-010 showed a groundedness judgement against the
needle isolates it exactly — 1 positive in 44 archived records, the claim
quoted verbatim, zero false positives — while no embedding metric can, because
fabrication and verbosity are the same operation on a whole-response
embedding (J-007).

The choice is not *whether* this is worth capturing but *when* and *in what
shape*, given that D-007 already settled "labels, not a fourth metric" and
build order puts the taxonomy at steps 3–5, after a failure corpus exists.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Wait for the taxonomy (build order 3–5) | One coherent label system, frozen from an observed inventory | The one observed instance stays unmeasured; every run archived meanwhile is another run that cannot be re-analysed for it, since the judge output is not stored |
| A `grounding_score` float in `metrics` | Fits `EvaluationResult(name, score: float)`; no schema pivot | Explicitly rejected by D-007 — compresses a *kind* into a magnitude, and 0.4-grounded says nothing about what was invented |
| A boolean label + evidence string in the judge's existing call | Captures it now, costs no extra model call, and the evidence makes it auditable offline | Ships one label before the taxonomy exists, so it is not yet reconcilable with a `primary_label`; couples results to judge capacity (J-010) |

**Decision.** The third, scoped deliberately narrow: `grounded` (bool) and
`unsupported_claim` (str) on the **existing** judge call, recorded in
`evaluation_details.llm_judge` — *not* in `metrics`, and *not* in a
`classification` block.

What decided it: the marginal cost is zero. D-008 already committed to the
label tier riding the judge call rather than making a second one, and the
judge already receives everything it needs — `case.metadata["needle"]` has
been populated since the benchmark was written. So this is the cheapest
possible probe of D-007's central bet, on real data, before the expensive
machinery is built.

Keeping it out of `metrics` is the load-bearing half. `metrics` is a
`dict[str, float]`; putting a boolean there would be D-007's rejected option
wearing a different hat, and would make `grounded` averageable — a "mean
groundedness of 0.97" is exactly the summary that destroys the information.

**Rejected.** *A grounding float* — see D-007; `Revisit if:` a genuine
*degree* of grounding is ever needed, and then alongside the label, never
instead of it. *Waiting for the taxonomy* — `Revisit if:` this turns out to
constrain the taxonomy's shape at freeze time; the label is deliberately
recorded outside any `classification` block so it can be re-derived into one
rather than having to be migrated out of it. *Removing
`semantic_similarity` at the same time* — the user's explicit instruction is
to keep it for now; D-006 stays **open**, and this entry does not close it.

**What this changes about what is measured.** NIAH stops being a pure
retrieval task and becomes retrieval *plus* faithfulness. Under the previous
definition the J-008 response is **correct**; under this one it is correct
but ungrounded. That must be stated in any result, and it is why `correct`
and `grounded` are two fields rather than one merged verdict — the old
question is still answerable from the new records.

**Predicted.** Three falsifiable claims.

1. `grounded` will look inert on current-shape runs — J-010 measured a 2.3%
   base rate, and 41 of 44 archived predictions are bare code strings with
   nothing to be ungrounded about. If it fires on more than ~5% of a
   bare-string run, the judge is over-triggering and the prompt is wrong.
2. Enabling it with a judge below the capacity floor will report
   `grounded: false` on nearly everything (J-010: `qwen3:0.6b` scored 1/7).
   This is the failure mode to watch for, and it manufactures a failure mode
   rather than missing one.
3. At freeze time the taxonomy will need a core label this hypothesis does
   not contain — `UNGROUNDED_JUSTIFICATION` or similar — because a correct
   answer with an invented justification is not `WRONG_ANSWER`,
   `FORMAT_VIOLATION`, `NON_ANSWER` or `OK`.

**What we got.** not yet.

---

## D-011 — Make `lexical_exact_match` an assertion check, not a containment check
Status: accepted, executing
Decided: 2026-09-03 | Trigger: J-013, J-012 | Changes what is measured: **yes** — the metric's semantics

**The problem.** `LexicalEvaluator` scores `1.0` whenever the expected string
appears anywhere in the response, so a model that quotes the code in order to
*deny* it scores full marks. 16 of 330 records in `2bfcd3f32b11`; reported
accuracy 0.788 against a corrected 0.739, and the depth-1.0 cell inflated
from 0.33 to 0.63. See J-013 for the evidence, J-012 for why the rejecting
responses exist at all.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Leave it; document in LIMITATIONS | Archive stays comparable; zero risk | The headline metric is known-wrong in a direction that flatters the model, and every figure needs a manual asterisk |
| Require the response to be *only* the expected answer (modulo whitespace/punctuation) | Unambiguous; trivially deterministic | Fails every correct sentence-form answer — 3 of 15 in `85d237650c49` — trading a false-positive problem for a much larger false-negative one |
| Containment **minus** a denial check: contains the answer AND does not repudiate it | Removes the observed false positives, keeps sentence-form answers | A hand-written denial pattern is a heuristic; it will have its own false positives and needs its own evidence trail |
| Drop the metric, rely on the judge | One fewer wrong number | The judge is a model call, non-deterministic, and unavailable offline. This is the one metric that is free and replayable |

**Decision.** The third: containment, with a repudiation guard. A response
scores `1.0` when it contains the expected answer **and** does not assert
that the answer is absent, fictional, or an artifact.

What decided it: the rule tier has to be **replayable offline over stored
JSONL** (build-order step 4), which rules out the judge, and a free
deterministic check that is wrong 5% of the time in the flattering direction
is worse than one that is wrong less often in a stated direction. The
exact-only option was rejected on measured evidence rather than taste — 3 of
15 records in `85d237650c49` are correct sentence-form answers that it would
score 0.

The guard is deliberately **narrow**: it fires only on explicit repudiation
of the answer's existence or validity, not on hedging, not on verbosity, and
not on the model discussing the text. Over-broad denial matching would
reintroduce false *negatives*, which is the failure mode this project can
least afford — a false negative looks like a model failure and would be
written up as one.

**Rejected.** *Leave it* — `Revisit if:` the guard proves less accurate than
the bug it replaces, measured on the same 330-record file. *Exact-only* —
`Revisit if:` the task is ever restated as "emit the code and nothing else",
which would be a different benchmark. *Drop it* — `Revisit if:` the rule tier
lands and subsumes it; at that point `lexical_exact_match` becomes one input
to `OK` rather than a reported metric. `Revisit if:` also — the guard needs
per-language work the moment a non-English benchmark family exists.

**What this changes about what is measured.** `lexical_exact_match` stops
meaning "the expected string occurs in the response" and starts meaning "the
response asserts the expected answer". **Values are not comparable across
this change.** For the 42 archived records with bare-code answers the two
definitions agree, so the practical break is confined to runs where a model
argues with the prompt — which is exactly the two llama runs and the reason
this matters.

**Predicted.** Three falsifiable claims.

1. On `2bfcd3f32b11` the metric drops from 0.788 to **0.739** — 16 records
   flip from 1.0 to 0.0, 9 of them at depth 1.0.
2. No record currently scoring 0.0 flips to 1.0, since the guard only ever
   removes credit.
3. On every other archived file the metric is **unchanged**, because no other
   run contains a repudiating response.

If (2) or (3) fails, the guard is over-broad and the decision is wrong.

**What we got.** (1) nearly — **15** flips, not 16, giving **0.742** rather
than 0.739. (2) and (3) exactly: zero 0.0 → 1.0 flips anywhere, and all
eleven other files unchanged, so the guard is not over-broad on any evidence
available.

The missing 16th is the more useful half. J-013's count came from a looser
ad-hoc analysis regex matching the bare substrings `not a real` and
`is a mistake`; the shipped guard requires them qualified. The response it
spares says *"the important secret … is the secret ingredient
QUANTUM-LEAP-99, which is not a real ingredient but a fictional one"* — which
**asserts** the answer and then editorialises, unlike the other 15, which
deny it exists. On reading it, the guard is right and the prediction was
wrong. See J-014.

Two things this validated beyond the metric. The prediction was only
falsifiable because it was written before the code landed — had the guard
been shipped first, 15 would simply have looked like the answer. And the
distinction the guard draws turns out to be exactly the D-010 boundary:
denial of the answer belongs to `lexical_exact_match`, unsupported commentary
around a correct answer belongs to `grounded`.

---

## D-012 — Content-addressed case identity: two keys, a versioned component set
Status: accepted, executing
Decided: 2026-09-04 | Trigger: J-004, J-005, D-009, invariant 11 | Changes what is measured: no

**The problem.** `case_id` is `niah_{target}_{depth:.2f}_{counter:04d}` where
the counter runs over the whole sweep and increments only on non-skipped
cases. It shifts when `--needles` or `--depths` change, when a cell is
skipped, or when a target is dropped — and the needle is not in it at all
(J-004). Results cannot be joined across runs, which blocks the question the
project exists to answer: *do different models fail on the same inputs?*

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Fix `case_id` to include the needle and drop the counter | One key, no new fields | One key cannot answer both "same design point" and "same bytes". After the §1.1 tokenizer fix those diverge permanently, and a single key silently picks one meaning |
| `case_key` only (grid coordinate) | Survives construction changes; the only key the pre-1.2 archive can ever carry | Cannot assert two models saw *identical* input, which is what a clean cross-model claim needs |
| `case_fingerprint` only (content address) | Strict comparability | Correctly stops matching after any construction change, so it cannot express "same cell, different build" — and archived records can never have one |
| **Both**, with a versioned component set | Each answers its own question; a claim states which join it used | Two fields to keep consistent; the component set becomes a permanent commitment |

**Decision.** Both keys, plus `prompt_sha256`, plus a `FINGERPRINT_VERSION`
stamped into the digest.

Three sub-decisions that are the actual content:

1. **`case_key` carries the experimental arm.** CLAUDE.md documents
   `niah/t{target}/d{depth:.2f}/n{needle_index}`. That string is *identical*
   for the `marked` and `bare` arms of the same cell once D-013's templates
   land — a key that silently pools two experimental conditions is J-004
   again, one level up. The format is extended to carry template and tail
   guard. A key that is unsafe to use alone will be used alone.
2. **The component set is complete from v1.** `needle_template`,
   `tail_guard_tokens` and `distractors` are components *now*, taking their
   present values (`"marked"`, `0`, `[]`), even though nothing can vary them
   yet. Adding a component later would change every fingerprint for
   byte-identical inputs and invalidate the D-009 baseline the moment it was
   captured.
3. **Hardware is NOT a component.** See D-013. The fingerprint addresses the
   model's *input*; the machine does not change the input, and including it
   would stop the same case joining across machines — destroying the
   comparison D-013 exists to enable.

Components: experiment, `prompt_sha256`, system prompt, expected answer,
needle, target tokens, depth (formatted to 2dp as a *string*), tokenizer
provider and name, `filler_sha256`, needle template, tail guard, distractors.

Depth is a formatted string because `0.1 + 0.2` and `0.3` are different
components under `repr`, and a fingerprint that depends on how a float was
arrived at is not a fingerprint. The serialiser rejects raw floats anywhere
in a component set rather than trusting callers to remember.

**Where it is computed.** `core/case_identity.py` owns *how* a component set
is canonicalised and hashed; `benchmarks/.../NIAH/identity.py` owns *which*
components NIAH depends on. Not `core/runner.py` — CLAUDE.md's scope rule is
that anything in `core/` mentioning needles is in the wrong place, and only
the benchmark holds the prompt at the moment it is built.

**Archived records get `case_key` but `case_fingerprint: null`.** The prompt
was never stored and cannot be reconstructed, so null is the honest value and
those twelve files join on `case_key` only. This is invariant 8's shape
applied to identity: a synthesised fingerprint would assert byte-equality
that was never verified.

**Rejected.** *One key* — `Revisit if:` the §1.1 fix is abandoned, which
would keep the two meanings permanently aligned. *`case_key` as documented in
CLAUDE.md, with a separate `arm` field* — the arm field would be optional,
and every join that forgot it would silently pool conditions; `Revisit if:`
the template axis is removed entirely. *Storing the prompt itself instead of
a digest* — a 128k-token haystack per case makes the archive unusable;
`Revisit if:` a compact reconstruction recipe (corpus digest + slice bounds)
proves insufficient for re-deriving prompts offline.

**A known weakness, recorded rather than solved.** `needle_index` is a line
number in `needles.txt`. Inserting a needle mid-file silently renames every
key below it — the same class of defect as `case_number`, just slower-moving.
Kept for readability, with `needles_sha256` recorded per run as a tripwire and
a LIMITATIONS entry whose removal condition is a content-addressed needle
component.

**Predicted.** All 12 archived files migrate to 1.2 with a non-null
`case_key` and a null `case_fingerprint`. Two runs of the same sweep on the
same machine produce identical fingerprints per case; changing `--needles`
changes `case_id` but not `case_key` or `case_fingerprint`.

**What we got.** not yet.

---

## D-013 — Record the host machine, and refuse to guess it when Ollama is remote
Status: accepted, executing
Decided: 2026-09-04 | Trigger: §2.1–§2.4, J-011 latency, imported result files | Changes what is measured: no

**The problem.** Nothing records which machine a run happened on. Latency is
therefore uninterpretable — `llama3:8b` at 6.5–8.0 s/case and `llama3.2:1b`
at 22–176 s/case are not comparable, and neither is comparable with the qwen
runs, because all three came from different systems and no record says so.
More sharply: results now arrive from machines we do not control, and a
diagnostic not captured in the record is permanently unavailable. That was not
hypothetical — the truncation hypothesis for `2bfcd3f32b11` could not be
tested because llama3 is not installed on this host.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Nothing; note the machine in the commit message | Free | Not attached to the data; useless for grouping, lost on import |
| One flat `host` block, detected once | Simple | Conflates "what machine is this" with "what was it doing at the time" — the first never changes, the second is the interesting confound |
| Static `machine` + a run-start `snapshot` | Separates identity from contention | Contention *during* a run is still unmeasured |
| Per-case snapshots | Full contention trace | An `nvidia-smi` subprocess per case — 330 in the J-011 run — to measure something that mostly does not move, on a host the preflight already says is memory-bound |

**Decision.** Static `host.machine` plus a single `host.snapshot` at run start.

Most of the detection already exists and is being thrown away:
`core/health.py` calls `total_ram_bytes()`, `available_ram_bytes()`,
`swap_total_bytes()`, `gpu_names()` and `available_vram_bytes()` for the
doctor report and discards all five. Genuinely new: CPU model and core count,
platform and kernel, *total* VRAM, driver version.

**The decision that actually matters: refuse to guess when Ollama is remote.**
`OLLAMA_HOST` can point anywhere, and `/proc/meminfo` then describes the
client, not the machine that ran inference. Writing the client's specs into
such a record is **worse than recording nothing**, because it looks
authoritative and would be grouped on. When the resolved host is not
localhost, `host.machine` is `null` with `machine_source: "remote"` and the
host string recorded. Ollama's API does not expose remote hardware, so null is
the only honest value.

This is invariant 8's principle applied to provenance: absent is data,
fabricated-but-plausible is corruption.

**Rejected.** *Per-case snapshots* — `Revisit if:` a run's latency variance is
itself the object of study, at which point the cost is justified.
*Recording client specs regardless of host* — `Revisit if:` Ollama ever
exposes server hardware, which would make it a real measurement rather than a
guess. *Putting hardware in `case_fingerprint`* — see D-012; it would break
cross-machine joins, which is the opposite of this entry's purpose.

**Predicted.** Two falsifiable claims. Accuracy grouped by
`host.machine` should show **no** effect — the same model on the same cases
should score the same anywhere. If it does not, something is wrong (silent
truncation, a different quantization, contention), and finding that is worth
more than the block costs. Latency grouped by machine should show a large
effect, and become interpretable for the first time.

**What we got.** not yet.

---

## D-014 — Do not migrate `metrics.lexical`; record metric definitions instead
Status: **open** — the refusal is decided, the replacement is not
Decided: 2026-09-04 (refusal only) | Trigger: J-005, D-011 | Changes what is measured: no

**The problem.** J-005 found three record shapes all declaring `"1.0"`, the
worst being a silent rename of `metrics.lexical` → `metrics.lexical_exact_match`
that makes a naive aggregation under-report rather than error — confirmed
doing exactly that in J-014, where three archived files silently contributed
0.000. The obvious repair is a migration that renames the key.

**That repair is now actively harmful.** D-011 changed what
`lexical_exact_match` *means*: archived `lexical` values are **containment**,
post-D-011 values are **assertion**. Renaming would file containment numbers
under a name that means something else — a worse J-005 than the one being
fixed, because the resulting archive would look uniform and be wrong.

There are therefore **three** distinct metric definitions in the archive
sharing two names:

| Definition | Recorded as | Meaning |
|---|---|---|
| pre-rename | `metrics.lexical` | `expected in response` |
| post-rename, pre-D-011 | `metrics.lexical_exact_match` | `expected in response` |
| post-D-011 | `metrics.lexical_exact_match` | contains AND does not repudiate |

**Options.** Rename in the migration (rejected, above). Leave it entirely
(the metric keyspace stays lying). Record a `definition_version` per metric
per run, so a reader can tell the three apart. Or version the metric *name*
itself (`lexical_exact_match_v2`), which is self-describing but churns every
downstream consumer on each change.

**Decision — the refusal only.** The 1.1 → 1.2 migration does **not** rename
the key. What replaces it is not decided: `definition_version` and a versioned
metric name are both live, and choosing between them properly needs the
reporting layer (§5.1) to exist first, since that is the only consumer whose
requirements would settle it.

Recorded now, unimplemented, because once the migration ships without the
rename the reason will look like an oversight rather than a choice — which is
precisely the failure mode invariant 13 exists to prevent.

**Rejected.** *Renaming in the migration* — `Revisit if:` the pre-D-011 and
post-D-011 definitions are ever shown to agree on the whole archive, which
J-014 already disproves for `2bfcd3f32b11` (15 records differ).

**Predicted.** Any cross-run aggregation of `lexical_exact_match` written
before this is resolved will be wrong in one of two ways: dropping a third of
the archive, or pooling two definitions. The reporting layer must therefore
refuse to pool metrics across definition boundaries rather than leaving it to
the caller.

**What we got.** not yet.

---

## D-015 — `case_key` addresses the needle by digest, not by line index
Status: accepted, executing | supersedes D-012's needle-index sub-decision
Decided: 2026-09-04 | Trigger: D-012, §1.15, found while implementing the migration | Changes what is measured: no

**The problem.** D-012 chose `n{needle_index}` for the needle segment of
`case_key`, accepted §1.15's positional-identity defect, and mitigated it with
a `needles_sha256` tripwire. Writing the 1.1 → 1.2 migration showed that
choice does not work, for a reason the decision missed.

**A migration must be a pure function of the record.** Archived records store
`case.needle` as *text*; they do not store its index. Deriving `n{index}` for
an archived record therefore requires reading `needles.txt` at migration
time — which makes the migration depend on a mutable data file, so the same
record migrates to different keys depending on when it is migrated. And since
archived and fresh keys must match for the join to mean anything, an impure
migration here is not a cosmetic problem: it silently produces keys that do
not join.

**Options.** Keep the index and let the migration read `needles.txt`
(impure — rejected). Give archived records no `case_key` at all (rejected:
`case_key` is the *only* key those twelve files can ever carry, per D-012).
Address the needle by a short digest of its text, derivable from any record
that stores the needle — chosen.

**Decision.** `n{sha256(needle)[:8]}`. The needle text is in every archived
record, so the migration is pure, and archived keys match fresh keys exactly.

The reason this was not the first choice is readability: `n3` is legible in a
log line and `n1f4c8a02` is not. That was the wrong trade. A key is read by
joins far more often than by people, and D-012's own argument — "a key that is
unsafe to use alone will be used alone" — applies here too.

**This resolves §1.15 rather than mitigating it.** A digest is content-
addressed, so inserting or reordering `needles.txt` no longer renames any key.
The `needles_sha256` tripwire is kept anyway: it is nearly free and it detects
corpus edits that a per-needle digest cannot, such as a needle's text being
changed in place.

**Rejected.** *Index plus an impure migration* — `Revisit if:` never; a
migration that reads mutable state outside the record is a defect regardless
of the field it computes. *No `case_key` for archived records* — `Revisit if:`
the archive is abandoned, which would remove the only reason to migrate it.

**Predicted.** `migrate_record` has no imports from `benchmarks/` and no file
I/O — checkable by inspection, and the property a test should assert. All 12
archived files produce keys that join with a fresh run of the same cell.

**What we got.** not yet.

---

## D-016 — Layered config: a TOML file, with measured and operational settings kept structurally apart
Status: accepted, executing
Decided: 2026-09-06 | Trigger: §1.6, §1.9, §1.12, J-012, the three-machine fleet | Changes what is measured: no — but it is the precondition for three experiments that do

**The problem.** Two problems that turn out to be one.

*The measured variables are hardcoded.* `NiahBenchmark.question` and
`.system_prompt` are class attributes; the needle marker is an f-string in
`generator.py`; `FILLER_PATH` and `NEEDLES_PATH` are module constants in
`run.py`. §1.9 measured needle wording at **19 points of accuracy** and J-012
found the model disputing the `[IMPORTANT SECRET]:` marker as an artifact — so
these are first-order experimental variables that currently cannot be varied,
recorded, or hashed. The marker-ablation, corpus-similarity and multi-needle
experiments are not expressible without changing this.

*Three machines must run comparable work.* A fleet sharing a repo needs
per-machine execution settings (memory headroom differs) without per-machine
*measurement* settings (§1.6 is already the case where auto-sizing silently
gives two machines different sweeps).

**Options.**

| Option | Gives | Costs |
|---|---|---|
| More CLI flags | No new machinery | A 20-flag invocation is not reviewable, not diffable, and not shareable across a fleet; and it is retyped — differently — on every machine |
| `.env` file | Familiar; one file | Everything is a string needing parsing; lists and per-machine profiles need a prefix convention; needs a new dependency or a hand-rolled parser; **and env vars are invisible in shell history and in diffs** |
| YAML file | Most expressive for nested matrices | A new runtime dependency for something `tomllib` already does |
| **TOML file + env for session properties** | Structured, typed, diffable, committable, hashable; `tomllib` is stdlib on 3.12 | A precedence order to get right, and one subtle argparse trap |

**Decision.** A committed `probebench.toml`, read with `tomllib`, validated
with pydantic (already a dependency), layered:

```
CLI flag > environment > [machine.<name>] ⊔ [experiment.<name>] > [defaults] > dataclass defaults
```

Four sub-decisions carry the entry.

1. **`[machine.*]` and `[experiment.*]` are disjoint types, not ordered
   layers.** Separate pydantic models with non-overlapping key sets. A machine
   section *cannot* express `depths`, so "the same command measures the same
   thing on every box" is a type error rather than a review comment. This is
   the whole reason the file is safer than a pile of flags.

2. **No environment variable may set a measured parameter**, and the loader has
   no code path by which one could. Env carries session properties only —
   `PROBEBENCH_CONFIG`, `PROBEBENCH_MACHINE`, `OLLAMA_HOST`, and the two Ollama
   KV variables which are **read and recorded, never written by us** (J-016).
   An env var is invisible in shell history, invisible in a config diff, and
   absent from the record unless something captures it: §1.12's exact
   mechanism with a weaker audit trail.

3. **`extra="forbid"` on every section.** A file that silently ignores
   `dephts = [0.0, 0.5]` is *worse than no file*, because the run looks correct
   in the archive and measured something else. Typo rejection is the entire
   safety argument, and it is the only thing pydantic is used for here —
   `RunConfig` stays a dataclass, per CLAUDE.md's explicit-dataclass
   convention.

4. **`kv_cache_type` lives in `[experiment.*]`, not `[machine.*]`.** It looks
   operational — a memory knob — but whether q8_0 KV degrades retrieval is
   unmeasured, so until it is measured it is a *measured variable* and must be
   pinned fleet-wide. This is the case that shows why the split has to be
   structural: a reviewer would have waved it through as a machine setting, and
   three machines would then have run three KV precisions and called it one
   experiment.

**The trap that would make the file silently inert.** `argparse` defaults are
indistinguishable from user-supplied values, so with `--depths` defaulting to a
list, CLI wins on every invocation and the file layer is dead on arrival.
**Every shared run option's default must become `None`**, with the real
defaults living in `core/config.py`. Recorded here because it is the single
change most likely to be got wrong, and because its failure mode is silence.

**Fingerprint interaction.** Config splits three ways: *input* (changes prompt
bytes → already in `case_fingerprint`), *sampling* (changes output at fixed
input → deliberately **not** in it, per D-012), *operational* (neither). The
first class needs no `FINGERPRINT_VERSION` bump because D-012 sub-decision 2
pre-registered `needle_template`, `tail_guard_tokens` and `distractors` as
components at their present values. A tripwire test — every field marked
`axis="input"` must be reachable from the component set — fires the moment
someone adds a measured key without hashing it.

**Rejected.** *`.env`* — `Revisit if:` the config surface ever collapses to a
handful of scalars, which the experiment programme makes unlikely. *YAML* —
`Revisit if:` a genuinely nested experiment matrix outgrows TOML's ergonomics;
the cost is one dependency, not a redesign. *More flags* — `Revisit if:`
never; the fleet is the disproof. *A TOML writer (`tomli-w`)* — the file is
hand-edited and reviewed, and the **resolved** config is serialised as JSON
into a run sidecar, so a writer would add a dependency and a second, drifting
representation of the same state.

**Predicted.** Three falsifiable claims. Day one, `probebench <model>
--dry-run` with the config present produces a byte-identical sweep to the same
command without it — the layer is a no-op until something opts in. A file
containing a misspelled key raises rather than running. And no `[machine.*]`
section in the committed file will need a key that changes what is measured;
if one does, the split is wrong and this entry should be revisited rather than
the key quietly moved.

**What we got.** All three held.

```
--target-tokens 4000 --depths 0.0,0.5,1.0                  -> 3 cases
--target-tokens 4000 --depths 0.0,0.5,1.0 --machine laptop-a -> 3 cases
--experiment-profile calibration                            -> 18 cases
```

The machine profile moved nothing, which is the type-level split working
rather than being remembered. `dephts = [0.0]` raises
`Config error: ... defaults.dephts / Extra inputs are not permitted`, naming
the key. And all three committed `[machine.*]` sections needed only
`memory_headroom_fraction` and `two_phase`.

**A stronger check than any of the three, added during implementation.** A
freshly generated case reproduces the archived fingerprint exactly:

```
case_key         niah/t4000/d0.00/n06bfb731/marked/g0
case_fingerprint 668cb8223f5f1802c03ce303310de27382220a8d6104cb1c81d382da9863116d
```

byte-identical to record `db8099fc714c`. That is the property that matters —
the config layer made `question` and `system_prompt` configurable *without*
disturbing what the previously hardcoded values hashed to, so the 402-record
archive still joins with anything run after it. There is now a test asserting
`NiahParams`' defaults equal `NiahBenchmark`'s class attributes, because that
equality is the whole basis of the guarantee and nothing else would catch it
drifting.

**One thing the entry did not predict, and should have.** Turning the argparse
defaults to `None` broke `_prepare`, which read `args.output_dir`,
`args.tokenizer` and `args.embedding_model` directly for the health check and
got `None`. The trap was recorded; its *second-order* consequence — that other
call sites also depended on argparse supplying real defaults — was not. The
fix improved things: `_prepare` now takes the resolved settings, so the health
check validates the models and paths the run will actually use, which it could
not do before. Worth generalising: **when a layer takes over supplying
defaults, every existing reader of the old defaults is a candidate breakage**,
and `grep` for the attribute is the cheap way to find them.

---

## D-017 — Measure KV precision from the API rather than trusting a flag
Status: accepted, executing
Decided: 2026-09-07 | Trigger: J-016, J-018 | Changes what is measured: no — it records what was always true

**The problem.** `--kv-cache-type q8_0` feeds only the memory estimator and is
then written into the record as though it described the run (J-016). The
planned q8_0-vs-f16 experiment is a paired comparison of the same
`case_fingerprint` under two KV precisions, so if the flag does not determine
the precision, both arms are f16 and the experiment measures noise while
appearing to measure quantisation.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Read `OLLAMA_KV_CACHE_TYPE` from our environment | Trivial | **Wrong.** The daemon is a systemd service under user `ollama`; our env is a different process's env (J-018). Produces a confident field unrelated to the run |
| Read the daemon's `/proc/<pid>/environ` | Correct in principle | Needs same-user or root, Linux-only, local-only. Verified unreadable on the default install; useless for the two fleet machines that are not ours |
| **Measure it: differential `/api/ps` size across two context sizes** | Works remotely, works against a service daemon, works when someone else configured the box | Two extra model loads at run start; a small unexplained error; needs GGUF geometry, which we already extract |
| ProbeBench launches its own `ollama serve` | Full control of the environment | Server lifecycle management; conflicts with a service already holding `:11434`; antisocial on a shared college machine; reintroduces J-002's two-servers-one-port trap |
| Record the request plus a confidence marker, verify nothing | Nearly free, honest | Leaves the q8_0 experiment resting on an unverified assumption about a server we cannot see |

**Decision.** Measure it, and fall back to the confidence marker when the
measurement cannot be taken.

What decided it: the fleet. Two of three machines are not ours, and one of
those is a shared college PC where we will not have root and did not configure
the daemon. Every option except measurement degrades to "unknown" precisely
there — which is where most of the compute is going to run.

The probe loads one model at two context sizes and differences the reported
`size`. Weights and compute buffers do not depend on context, so they cancel
exactly; the residual divided by `2 x n_layers x n_kv_heads x head_dim` is
`bytes_per_element`. Measured 1.932 against a true 2.0 (J-018).

**What gets recorded** — four fields, because "what we asked for", "what is
true", and "how well we know" are three different things and collapsing them
is the defect this entry exists to fix:

- `kv_cache_type_requested` — what the flag or config asked for
- `kv_cache_bytes_per_element_measured` — the raw probe result, e.g. `1.932`
- `kv_cache_type_effective` — the classification, or `null`
- `kv_cache_probe` — `"measured"`, or `"unavailable: <reason>"`

The existing `kv_cache_bytes_per_element` keeps its meaning — the *estimator's*
assumption — and is no longer the only KV field, which is what made it
misreadable.

**A run whose requested and measured precisions disagree refuses to start.**
That is the check J-016 wanted, aimed at the server instead of at a guess.

**Rejected.** *The environment variable* — `Revisit if:` never as ground
truth; it may be recorded as a hint alongside the measurement, but a hint is
not a fact. *`/proc` inspection* — `Revisit if:` a run is known to be local,
same-user and Linux, where it is a free cross-check on the probe rather than a
replacement. *Launching our own server* — `Revisit if:` a result depends on a
serving configuration Ollama's daemon cannot be asked for at all, which would
be a much stronger reason than this one. *Recording the request only* —
retained as the fallback, never as the primary.

**Tolerance and its justification.** Classification uses a +/-15% band around
2.0, 1.0 and 0.5. The observed error is 3.4% and the hypotheses are 2x apart,
so the band is loose enough to absorb the unexplained residual and tight
enough that no two classes can ever both match. A measurement outside every
band records the raw number and classifies `null` rather than snapping to the
nearest — an unrecognised precision is data, not a rounding problem.

**Predicted.** Three falsifiable claims. On this machine, with no KV variables
set on the daemon, the probe reports ~1.9 and classifies `f16`. Setting
`OLLAMA_KV_CACHE_TYPE=q8_0` on the *daemon* and restarting it moves the
measurement to ~1.0 while our own shell environment stays empty — which is the
experiment that proves the env var was never the right thing to read. And a
`--kv-cache-type q8_0` run against an unmodified daemon now refuses to start
instead of archiving a mislabelled record.

**What we got.** Claims 1 and 3 hold. Claim 2 is not yet run — it needs the
daemon restarted with a changed environment, which is a deliberate act on a
machine, not something to slip into a verification pass.

```
KV cache precision measured: 2.080 bytes/element -> f16 (requested f16)   -> proceeds

KV cache precision measured: 1.932 bytes/element -> f16 (requested q8_0)
RuntimeError: KV cache precision mismatch: --kv-cache-type says 'q8_0' but the
server is running 'f16' (1.932 bytes/element). ...
```

The mislabelled record J-016 described is now unreachable: the run stops before
writing anything.

**The tolerance band earned its width, for a reason the entry did not
anticipate.** Two consecutive probes of the same unchanged server returned
**1.932** and **2.080** — a 7% spread between runs, not the ~3% single-shot
error J-018 reported. The reported `size` at a given context is not stable
across loads; the small-context reading moved by 100 MB between the two probes
(930,401,484 vs 1,034,975,968 bytes), most likely because how much of the model
sits in VRAM varies with what else the daemon has resident.

The classification is unaffected — both readings sit far inside the f16 band and
nowhere near q8_0's — but **the raw number is only good to about ±8%, not ±3%**,
and it should not be quoted as a precise measurement of anything. That is why
the raw evidence (`small_ctx`, `large_ctx`, and both sizes) is recorded per run:
the classification can be re-derived and the noise re-estimated offline without
re-probing.

This also narrows what the probe could ever do. Distinguishing f16 from q8_0 is
easy at ±8%. Distinguishing q8_0 from q4_0 — 1.0 against 0.5 — is still
comfortable. Detecting a *subtler* difference, or using the number as a
quantitative measure of cache overhead, is not supported by this instrument.

---

## D-018 — NIAH measures retrieval AND instruction-following
Status: accepted, executing
Decided: 2026-09-07 | Trigger: J-020, J-021, J-022 | Changes what is measured: **yes — the task definition**

**The problem.** The system prompt has always said *"Answer ONLY with the
secret code found in the text. Do not add any explanation."* Nothing measured
whether the model obeys, and 85% of the archive does not. The benchmark has
been instructing one task and scoring a different one.

**Options.**

| Option | Gives | Costs |
|---|---|---|
| Relax the instruction to match what is scored | One axis, no new machinery, archive stays interpretable | Throws away a signal that separates models more sharply than retrieval does, and 360 archived violations become uninteresting by fiat |
| Score compliance, keep it as the only headline | Simple | Collapses a 2×2 into a number dominated by whichever axis is lower |
| **Score both axes and report them jointly** | The task the models were actually given; two independent signals | A second metric; the archive's accuracy sentences stop meaning what they said |

**Decision.** Score both. The task is retrieval **and** instruction-following.

Four sub-decisions carry the entry.

1. **The rule scores FORM, never the expected value.** "Is the response the
   expected string alone" would make compliance imply retrieval — the
   composite collapses to its second term and the "obeyed the format,
   retrieved the wrong code" cell becomes unreachable *by definition*. J-022
   confirms that cell is empty (0 of 424) but the two rules score today's
   archive identically, so the better-defined one is free.
2. **The composite is derived, never stored.** `lexical_exact_match` is the
   cautionary case: its rule was rewritten (D-011), its key renamed (J-005),
   and D-014 records that three definitions now share two names with no way to
   tell which produced a value. A stored composite would be a fourth
   definition depending on two inputs whose definitions have already moved.
3. **`retrieved AND complied` is not a headline.** It is 0% for `llama3:8b`,
   which retrieves 74%. A number dominated by the lower axis hides which one
   failed — the defect this project exists to avoid. The reportable primitive
   is the **2×2 per model per context length**.
4. **The judge does not change.** R-003's clause — "framing is not an
   error" — stays; removing it re-breaks J-007. Compliance is a *syntactic*
   property of a string we hold in full, so an exact rule beats a stochastic
   judge that sees a 4,000-char truncation (§1.11) and has an unlocated
   capacity floor (§1.13). The judge was never wrong; it was answering the
   only question it was asked.

**On the name.** Called `instruction_compliance` by the user's choice. The
rule can only see *form*; obedience is a relation between a response and an
instruction, and no record at any schema version stores the instruction
(J-021). The gap is closed in the **report**, not the name: a compliance rate
is unavailable for any record lacking `case.system_prompt`, and the loader
exposes no method returning one. The response-form rate is always available.

**Rejected.** *A rule referencing `expected`* — `Revisit if:` never; it is
definitionally weaker. *A judge cross-check* — `Revisit if:` the rule's line
is ever contested by hand-labelling; note that adding a field to the judge
contract measurably moved `llm_judge` by 0.05 (D-010's `What we got`), so it
is not free. *A stored composite* — `Revisit if:` the reporting layer proves
unable to compose reliably, which D-014 already prescribes fixing in the
loader instead. *Relaxing the instruction* — `Revisit if:` the ablation below
shows the instruction is inert, in which case scoring obedience to an ignored
clause measures nothing.

**What this does to the archive.** It is **re-interpretable, not invalid.**
No metric changed meaning — `lexical_exact_match` measured retrieval and still
does. What becomes false is any *sentence* of the form "model X scores 74% on
NIAH", because NIAH now denotes a different task. The numbers survive; the
label on the axis does not. `instruction_compliance` is a pure function of
`response.predicted`, which every archived shape stores, so the archive can be
replayed rather than being lost.

**Predicted.** Three falsifiable claims.

1. Replaying the rule over the archive reproduces exactly 64 compliant and 360
   violations, and a bare-but-wrong answer scores compliance 1.0.
2. The two-system-prompt ablation on `llama3:8b` — the same corpus with and
   without the "Answer ONLY… " clause — will show the clause has **some**
   effect. If it frames at 100% under both, the instruction is inert, J-021's
   headline means something entirely different, and this entry's premise is
   wrong.
3. Compliance will prove more discriminating than retrieval across models —
   already visible as 0%–100% against retrieval's 74%–100%, though not yet at
   matched context (J-022).

**What we got.** not yet.

---

## D-019 — Close D-006: drop `semantic_similarity` from NIAH
Status: accepted, executing | closes D-006
Decided: 2026-09-07 | Trigger: J-022, D-018 | Changes what is measured: **yes** — a reported column disappears

**The problem.** D-006 has been open since 2026-08-31 with four options and no
decision, because every option looked like a loss. The strongest argument for
keeping the metric was that dropping it "loses the only continuous signal;
`lexical_exact_match` and `llm_judge` are both effectively binary".

**That argument is now dead, and the reason is a surprise.** J-022 shows
`semantic_similarity` separates bare answers from prose answers with **zero
overlap** — min 0.9918 against max 0.7977 over 424 records, holding within a
single model. It is not a continuous signal at all. It is a **step function**:
a near-perfect binary detector of response *form*, wearing a name that reads
as correctness.

So the metric was never the weak-correctness-signal D-006 was arguing about.
It was a strong form-signal, mislabelled — which is exactly why §1.5 could
observe it "ranking brevity" and read that as a defect.

**Decision.** Drop `EmbeddingSemanticEvaluator` from NIAH's evaluator list.
`instruction_compliance` (D-018) measures the same property **exactly**,
deterministically, offline, at zero cost, with a recorded rule version and a
four-way verdict rather than a float that must be thresholded.

Keep the class. It is family-agnostic, and on a future benchmark whose
expected answers are prose rather than a 12-character code, cosine similarity
against the expected text is a genuinely different and possibly useful
measurement. What is being dropped is its use in *this* family, where the
answer space is a single token and an exact rule dominates it.

Side benefit worth stating: one fewer embedding call per case, and one fewer
column in a summary table that put a form metric beside two correctness
metrics under a `context` axis — which is how it got misread for a month.

**Rejected.** *Rename and keep* (D-006 option c) — `Revisit if:` a family
appears where the rule cannot work; the class is retained precisely so this is
cheap. *Keep both and report their agreement as a tripwire* — attractive, but
it spends an embedding call per case to check an exact instrument with a noisy
proxy, and J-022 already establishes the agreement at n=424; `Revisit if:` the
rule's definition changes, at which point re-running the comparison once is
enough. *Redefine as a sentence-max* (D-006 option b) — `Revisit if:` never
for this family; it was an attempt to rescue a correctness reading the metric
was never delivering.

**Predicted.** Removing it changes no conclusion anywhere, because every
question it was answering is answered exactly by the new rule. Archived values
remain interpretable — better than before, since J-022 says what they actually
meant. If some analysis turns out to depend on it in a way the rule cannot
reproduce, this entry is wrong and the class is still there to restore.

**What we got.** not yet.

---

## D-020 — Build both counting and multi-hop; multi-hop first
Status: accepted
Decided: 2026-09-07 | Trigger: J-024 | Changes what is measured: **yes** — two new task families

**The problem.** The plan carried scoping controls for two proposed
experiments, with refusal conditions written before the data: drop counting if
accuracy at 1,000 tokens is below 0.8 for k ≤ 5; drop multi-hop unless the
largest fleet model clears 0.7. I argued in the plan that multi-hop should be
dropped, expecting a floor effect.

**Both controls passed** (J-024). Counting: `qwen3:4b` 5/5 for k ≤ 5, `qwen3:0.6b`
4/5. Multi-hop: `qwen3:4b` 4/4, `qwen3:0.6b` 3/4.

**Decision.** Build both. **Multi-hop first**, which reverses the plan's
ranking.

What decided the ordering is not the pass rate but the *shape of the failure*.
Multi-hop's single miss returned a **decoy** — a wrong answer whose cause is
identifiable from the response, because we planted the inventory and know what
every alternative was. Counting's misses are off-by-N with no recoverable
cause: answering 8 when the truth is 5 could be miscounting, double-counting,
or not counting at all, and the response carries no evidence which.

That distinction is the project's whole thesis. A diagnosable failure is worth
more than a graded one, and multi-hop produces diagnosable failures in a
four-line control.

**Rejected.** *Dropping multi-hop* — the position I argued for. `Revisit if:`
it floors at zero once context length is introduced, which the 1k control
cannot rule out; the control establishes only that a ceiling exists to degrade
from. *Dropping counting* — `Revisit if:` its errors stay opaque after the
rule tier lands; a task whose failures cannot be attributed is a scoring task,
not a diagnostic one. *Building either without a compliance column* —
`Revisit if:` never; J-024's k=7 case shows a content-correct answer scored as
a miss by a format-blind scorer.

**What this changes about what is measured.** Two new task families, each with
its own system prompt and answer space. Neither is comparable with NIAH: the
counting answer space is an integer, the multi-hop answer requires composition,
and both use different instructions. Cross-family accuracy comparison is
meaningless and a report must not offer it.

Note the counting answer space breaks an assumption `instruction_compliance`
currently makes — it raises on a multi-token expected answer, which is correct
for NIAH but means the counting family needs its own compliance rule, or a
generalisation of this one.

**Predicted.** Multi-hop degrades with context length *faster* than
single-needle retrieval, because two positions must both be attended rather
than one. If it degrades at the same rate, composition is not the binding
constraint and the extra hop is measuring nothing — which would be a useful
negative and would reopen the drop decision.

**What we got.** Partially, and more strongly than predicted — but the
prediction as stated is **still untested**, because only one context length has
been run.

At **4,000 tokens**, `NIAH_multihop` on `qwen3:0.6b` fails **16 of 50** (J-032).
Every NIAH metric in the entire 590-record archive is 1.0 at that length. So the
gap is not a difference in *slope*, which is what was predicted; it is a
difference in *intercept*. Composition is binding at the shortest length in the
grid, before context length has had a chance to do anything at all.

That is a better outcome than the prediction and a worse basis for it: a slope
claim needs the length sweep, and running it is now the point of the experiment
rather than a confirmation of it. Whether the two curves diverge, converge or
run parallel from a 32-point offset is open.

Two things the run settled that this entry did not anticipate. The failures
have **two distinct modes**, not one (9 non-answers, 7 planted-distractor
returns), and both are separable offline from the stored inventory with a regex
— which is build-order step 4's economic argument demonstrated rather than
asserted. And the largest effect in the run is **which registry entry the
pointer names** (80% failure at rank 2 versus 0–20% at ranks 0 and 3), an axis
this decision did not know existed and which is confounded with subject identity
by construction.

The counting family remains unbuilt and its compliance-rule problem, noted
above, remains unaddressed.

---

## D-021 — Extract a shared experiment pipeline rather than duplicating `run.py`
Status: executed → R-004
Decided: 2026-09-09 | Trigger: the multi-insert plan, Risk 2 | Changes what is measured: no

**The problem.** `NIAH_distractor` and `NIAH_multihop` need everything
`experiments/long_range_dependency/NIAH/run.py` does. That file is 485 lines and
is the single most heavily exercised path in the repo — every archived record
came out of it, and it carries R-002's two-phase split, invariant 2's memory
preflight, invariant 3's judge pinning, the KV probe ordering, and the
self-judging warning. None of that is NIAH-specific and all of it is
load-bearing.

Counted precisely, **exactly three things in it are NIAH-specific**:

1. the evaluator list (`LexicalEvaluator` is family-specific per §1.18;
   `InstructionComplianceEvaluator` and `OllamaJudge` are not),
2. `NiahParams(**config.experiment_params)` and the `NiahBenchmark(...)`
   construction that follows it,
3. two module constants, `FILLER_PATH` and `NEEDLES_PATH`, which are **already
   dead** — `NiahParams` supplies both paths and nothing reads the constants.

**Options.**

*A — Copy `run.py` twice.* Costs nothing today and is the fastest route to a
runnable experiment. Guarantees drift: the next fix to the KV probe ordering or
the two-phase split lands in one copy of three. R-002 and invariant 3 exist
because that ordering was got wrong once already, at the cost of a production
failure; three copies is three chances to regress it independently, in a file
whose correctness is invisible from reading it.

*B — Flag on the existing NIAH runner.* `--distractors k`. Smallest diff. Also
pools three different measurements under one `run.experiment` value, so a record
cannot say which task produced it without reading a parameter. The distractor
arm is **not** comparable with NIAH (§1.9 wording, different question, different
system prompt, discrimination rather than retrieval), so a shape that invites
pooling is a measurement-validity hazard, not a convenience.

*C — Extract `experiments/pipeline.py`, family plugs stay per-experiment.* The
generic runner takes a callable that returns cases, evaluators and the skipped
list; each experiment keeps a ~40-line `run.py` supplying only its three
specifics. One copy of the ordering. Costs a refactor of the one path
everything depends on.

**Decision.** C. The deciding reason is not deduplication — it is that the
ordering in `_run_niah` is *knowledge*, earned from two production failures, and
knowledge that exists in three copies is knowledge that will be wrong in two of
them. Option A's cost is not the duplicated lines, it is that the next person to
fix the runner has no way to know there are two other files to fix.

The refactor risk is real and is bounded by an existing guard: the byte-identity
test plus the 166-record fingerprint replay means a pipeline that changes what
NIAH produces fails before it is committed. That test was written for the
generator refactor and pays for itself a second time here.

`pipeline.py` goes at `experiments/pipeline.py`, **not** under a family — a
shared pipeline living inside `long_range_dependency/` would be a scope
violation of the same kind CLAUDE.md's "resist hardcoding NIAH assumptions into
`core/`" forbids, one directory down.

**Rejected.**
- *A, copy twice.* `Revisit if:` the two new families turn out to need a
  materially different ordering — in which case the divergence is real and
  should be explicit, not emergent.
- *B, a flag.* `Revisit if:` never on these grounds. A pooling hazard does not
  become acceptable with time. A flag would be fine for a knob that does not
  change the task, which `k` does.

**Predicted.** NIAH's output is byte-identical after the extraction — same three
haystack digests, same 166 fingerprints, same `668cb822…` for
`niah/t4000/d0.00/n06bfb731/marked/g0`. Each new experiment's `run.py` lands
under 60 lines. The dead `FILLER_PATH`/`NEEDLES_PATH` constants go with it,
since removing a second source of truth for a measured path is part of this
change rather than a drive-by.

**What we got.** Byte-identity held on every leg. The three digests reproduce,
the 166-record replay passes, `668cb822…` reproduces exactly, and — the strongest
check, because it exercises the generator refactor *and* the extraction together
— a **live 2-case run joined the archive on `case_fingerprint`, 2 of 2**, against
records generated by the pre-refactor code.

`run.py` came in at 119 lines rather than under 60. The prediction was wrong
because it counted only the plug wiring and forgot that `_build_evaluators`
carries the self-judging warning and D-019's retention note, which are family
knowledge and belong in the family file. 485 → 119 is the real number.

One thing the prediction missed entirely, found only by running it. The file
handler was attached to the NIAH runner's **own** module logger. After the
extraction the pipeline's messages and the family's messages live on *sibling*
loggers, so the self-judging warning — the one LIMITATIONS §1.2 depends on being
visible — would have been written to no file at all. Silently: nothing errors
when a log record has no handler.

Fixed by attaching to the `probebench` package logger, which is what a run log
should always have captured; the previous scoping also meant `runner.py`,
`ollama.py` and `preflight.py` never appeared in a `.log` file. **Generalisable
lesson: extracting a module splits a logger hierarchy, and the failure mode is
silence rather than an error.** Verified in the dry run — the warning now appears
under `…NIAH.run` in a log whose other lines are `…pipeline`.

The dead constants went, as predicted.

---

## D-022 — Uniform needle wording in the keyed families, and the comparability it costs
Status: accepted
Decided: 2026-09-09 | Trigger: §1.9, D-020 | Changes what is measured: **yes**

**The problem.** The distractor experiment asks a model to pick one code out of
k+1 present. For a wrong answer to *mean* "failed to discriminate", the decoys
have to be equally findable. NIAH's six needles are not: §1.9 measured a
**19-point** accuracy spread across their wording alone, larger than any context
effect in that run. Reusing them would confound "returned a decoy" with "that
decoy's sentence was easier".

**Options.**

*A — Reuse `needles.txt`.* Free, and keeps the arm on the same footing as NIAH.
Makes every distractor result uninterpretable for the reason above.

*B — One template, k+1 subjects.*
`The access code for {subject} is {value}.`, asked as
`What is the access code for {subject}?`. Only the subject varies, so a wrong
answer equal to a planted code is **necessarily** a discrimination failure.

*C — Reuse the needles but balance them across slots.* Randomise which needle is
the target so wording averages out across the grid. Preserves comparability with
NIAH and needs no new data file. Costs repeats we do not have — §1.4, one
Bernoulli sample per cell — so the averaging is nominal, and it makes each
individual case uninterpretable even though the aggregate is fair.

**Decision.** B. C is the interesting rejection: it is *statistically* the right
answer and is unavailable to us, because balancing requires repeats and §1.4
says we have none. Choosing B is choosing a clean per-case interpretation over
an aggregate fairness we cannot currently purchase.

⚠️ **This changes what is measured, and the change does not stay inside the new
experiment.** Uniform wording deletes the §1.9 variable *by construction*, so
**`NIAH_distractor` accuracy is not comparable with `NIAH` accuracy** — not
"approximately comparable", not "comparable with a caveat". Four independent
reasons stack: different needle wording, different question, different system
prompt, and discrimination rather than retrieval. Any figure putting the two on
one axis is wrong.

The k=0 cell is what makes this recoverable. Running the keyed family at k=0 is
NIAH's task with NIAH's structure and *only* the wording changed, so the
NIAH-to-keyed delta becomes a measured quantity rather than an assumed one.
That is the whole reason k=0 is in the grid and not treated as a degenerate
case.

The inventory carries `value` explicitly rather than re-parsing it.
`extract_expected_answer` splits on `" is "`, which happens to work on a keyed
needle and returns `'the one recorded for the north tower'` for a multi-hop
pointer. It exists for the legacy needle file and the new families should be
free of it.

**Rejected.**
- *A.* `Revisit if:` never — it is the confound the experiment exists to avoid.
- *C, balancing.* `Revisit if:` §1.4 is closed and runs carry repeats. Then
  balancing across slots becomes affordable and would give both a clean
  aggregate *and* comparability with NIAH, which B cannot.

**Predicted.** A wrong answer in the distractor arm is a planted value in a
majority of failure cases, rather than a fabrication. If most wrong answers turn
out to be *absent* from the prompt entirely, the uniform template has made the
task harder in a way not intended, and B needs revisiting.

**What we got.** not yet.

---

## D-023 — Build `NIAH_distractor` before `NIAH_multihop`, reversing D-020's order
Status: accepted
Decided: 2026-09-09 | Trigger: D-020, D-022 | Changes what is measured: no

**The problem.** D-020 decided to build both, multi-hop first, on the grounds
that its control (J-024) already produced a diagnosable failure — the one wrong
answer returned a decoy — while counting produced none. D-022 introduces a
dependency that argument did not account for.

**Options.**

*A — Multi-hop first, per D-020.* Honours the existing decision. Its first
results arrive without any measurement of what the uniform-wording change did,
so a multi-hop failure rate cannot be separated from the keyed-template effect.

*B — Distractor first.* Its **k=0 cell is the calibration** for D-022: NIAH's
task, NIAH's structure, uniform wording, nothing else changed. Running it first
turns "how much did the template change accuracy?" from an assumption into a
number, and multi-hop then inherits a measured baseline instead of an unmeasured
one. Multi-hop also *contains* the distractor mechanism — its registry blocks
are decoys — so building distractor first builds most of multi-hop.

**Decision.** B. D-020's reasoning is not overturned: multi-hop is still the
more diagnostically valuable experiment, and that is still why both are being
built. What changed is that D-022 created a calibration that only the distractor
family's k=0 cell can supply, and running multi-hop before it would spend the
compute and then need the baseline anyway.

Recorded as a separate entry rather than an edit to D-020, because D-020's
ordering was correct given what was known when it was made. The file records
what was believed at the time; that is the part that makes it worth keeping.

**Rejected.**
- *A.* `Revisit if:` the k=0 calibration turns out to be unnecessary — i.e. if
  the keyed-vs-legacy delta measures near zero, in which case ordering stops
  mattering and D-020's original ranking should govern.

**Predicted.** k=0 keyed accuracy lands within a few points of NIAH accuracy at
the same target tokens, because both are single-needle retrieval and the marker
is unchanged. A large gap would mean the wording change dominates, which would
make **every** cross-arm comparison in both new families unreportable and is the
single most important number to get early.

**What we got.** not yet.

---

## D-024 — Permute the registry so rank and subject identity vary independently
Status: accepted
Decided: 2026-09-10 | Trigger: J-032 | Changes what is measured: **yes**

**The problem.** J-032's largest effect is one nothing predicted: *which
registry entry the pointer names*. Rank 2 fails **80% at k=4 and 80% at k=8**,
at realised document depths of 0.685 and 0.314 — same rank, very different
position, identical failure rate. So it is not a position effect.

It is also not interpretable, because the registry is built in file order and
rank 2 is therefore **always Kingsley**. Three explanations fit the data equally
well and the design cannot separate them:

1. a middle-of-registry effect — ranks 0 and 3 are endpoints and both are easy,
   which is what primacy plus recency looks like;
2. a property of the token `Kingsley`;
3. a property of its value `ZBF-2094-HW`, the only planted code starting with Z.

Leaving it is not an option: it is the biggest effect in the project's only real
failure corpus, and every interpretation of that corpus depends on which of the
three is true.

**Options.**

*A — Rotate the whole needle file before slicing.* `needles[r:] + needles[:r]`,
then take k. One line. Changes which subject holds each rank — and also changes
the **set** of subjects in the registry, so subject set and rank move together
and the confound is replaced rather than removed.

*B — Fix the k-subset, cyclically rotate its order.* Registry stays
`needles[:k]`; rotation r assigns that fixed set to the depth slots starting at
offset r. Across k rotations every subject occupies every rank **exactly once** —
a Latin square. Subject set is held constant by construction, so rank is the only
thing moving.

*C — Random permutation with a recorded seed.* Maximum coverage of the
permutation space, and reproducible via the seed. Costs balance: with the case
counts we can afford, a random draw does not guarantee each subject visits each
rank, so a residual imbalance would have to be modelled rather than designed
away. §1.4 (no repeats) means we cannot buy our way out of that with n.

**Decision.** B. The deciding property is **balance at the n we can actually
run**, not coverage. A Latin square makes "rank" and "subject" orthogonal by
construction, so the contrast is a subtraction rather than a regression — which
matters because §1.3 (no seed control) and §1.4 (no repeats) mean we have no
error bars to model a residual imbalance against.

C is the right answer at large n and is unavailable for the same reason D-022's
option C was: balancing costs repeats we do not have.

**Two consequences that fell out, both good, neither designed for.**

`case_key` and `case_fingerprint` **need no change**. The key already carries
`b{digest}` over the `(id, depth)` pairs, and rotation is exactly a change to
which id sits at which depth — so the digest already distinguishes rotations,
verified directly. Rotation was a distinct design point in the identity scheme
before it was one in the code, which is what pre-registering `distractors` in
D-012 was for.

**Rotation 0 reproduces the current layout exactly**, so J-032's 50 archived
records stay joinable and become the r=0 stratum of the new design rather than a
superseded run.

**Also decided here: sweep the hop over the fixed subject SET, not over the
rotated list.** The old code took `registry[:needles_per_configuration]`, so
rotating would have changed *which subjects get tested as hops* at the same time
as it changed their ranks — reintroducing the confound in a subtler form. The
target set is now taken before rotation and is invariant to it.

**Rejected.**
- *A, rotate the file.* `Revisit if:` never on these grounds; it moves the
  confound rather than removing it.
- *C, random with a seed.* `Revisit if:` §1.3 and §1.4 are closed. With seeds
  and repeats, random permutation dominates — it covers the space a Latin square
  samples on the diagonal.

**What this changes about what is measured.** The grid gains an axis:
(length × depth × k × **rotation** × hop). At k=4 with full balance that is 4x
the cases. Registry layout is now a *controlled variable* rather than a constant,
which means **J-032's rank figures describe one layout and are not general** —
they are the r=0 cell of a design that did not exist when they were measured.

**Predicted.** The 80%-at-rank-2 effect **follows the rank, not Kingsley**. If it
does, the reading is positional and the mechanism is about where in a list the
model looks. If it follows Kingsley across rotations, the effect is lexical and
the uniform-template argument of D-022 is incomplete — needles can be uniform in
wording, token count and shape and still differ in difficulty, which would be a
more interesting and more inconvenient result. A third outcome — the effect
disappearing under rotation — would mean it was an artifact of the single fixed
layout, and J-032's rank paragraph should be withdrawn.

**What we got.** not yet.
