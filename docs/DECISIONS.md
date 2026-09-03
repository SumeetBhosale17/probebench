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
