# Articles

Drafts written for a broader audience, derived from the JOURNAL / DECISIONS
record. Per CLAUDE.md, a draft is written when a JOURNAL entry reaches
`Disposition: publishable`, when an R-00n lands, or when a D-00n's
`What we got` is filled with a real result.

**A draft here is not published.** Writing the file is a docs edit; posting it
is a visible action on someone's account and gets confirmed separately.

## Written

| Piece | Shape | Evidence |
|---|---|---|
| *(published by Sumeet)* — the KV cache allocation crash | incident → arithmetic → preflight | J-001, R-001 |
| [the-flag-that-configured-nothing.md](the-flag-that-configured-nothing.md) | a flag that never took effect → why the obvious fix was wrong → measuring the server instead | J-016, J-018, D-017 |
| [the-benchmark-was-the-bug.md](the-benchmark-was-the-bug.md) | 70 failures, of which most were caused by our own test design | J-011, J-012, J-013, J-014 |

## Queued, with the evidence already in hand

| Piece | The hook | Evidence | Why not yet |
|---|---|---|---|
| **The judge that graded 100 out of 1** | An LLM judge asked for 0.0–1.0 returned `100.0`; the framework refused it rather than rescaling. Then the "capacity floor" diagnosis turned out to be a confounded control — the same small judge worked fine once the *prompt* was fixed | J-006, J-009, R-003, D-005 | Ready to draft. Strongest methodology piece we have: the wrong conclusion is the content |
| **Absent is not zero** | A failed evaluator leaves its metric missing, never `0.0`, because scoring a crash as zero biases every aggregate downward. The same principle then reappeared five times: unmeasured KV precision, unknown hardware, unverified groundedness, underivable fingerprints | invariant 1, D-003, D-010, D-012, D-013, D-017 | Ready to draft. The most reusable idea in the project |
| **Three record shapes, one version number** | A schema that nobody read for a year; a metric renamed silently so aggregation under-reports instead of erroring | J-005, J-014, D-014 | Ready once the reporting layer lands and can show the damage concretely |
| **The metric that was measuring the right thing under the wrong name** | `semantic_similarity` was written off as broken — it "ranked brevity, not correctness". It turned out to separate compliant from non-compliant responses with **zero overlap** across 424 records. A defect under one task definition, a validated instrument under another | J-022, D-019, §1.5 | Ready to draft. The best "read your own data again" story in the project |
| **We told the model to answer with one word. 85% of the time it didn't, and we never noticed** | A user asked why the judge liked one response. The system prompt said "answer ONLY with the code"; nothing measured whether it obeyed; `qwen3:4b` obeys 37/37 and `llama3:8b` 0/330 | J-020, J-021, J-022, D-018 | Ready to draft once the context-matched run closes §1.17 |
| **Your context limit is your desktop session** | A model claiming 262k context; a machine that reported 53,938 — because the budget reads `MemAvailable`, so the number was measuring a browser | plan output, §2.2 | Wants the headless-vs-desktop comparison actually run |

## How to write one

The template is the KV cache piece, and it is four beats:

1. **An incident** — something concrete that happened, with the raw output.
2. **A mechanism** — why it happened, not just that it did.
3. **The arithmetic or evidence that proves the mechanism** — the part that
   would fail if the explanation were wrong.
4. **A generalisable lesson** — what a reader takes to their own work.

What it is *not*: a results announcement, a feature list, or a claim the
record does not support. If a finding is still open, the article says so.
J-003 stands — no genuine retrieval failure has been isolated from an
instrument artefact yet — so no piece may claim we have found model failures.

Length 1,200–1,800 words. Show real output, including the ugly bits. Name the
wrong turn: every piece here is stronger for the paragraph where we were
wrong.
