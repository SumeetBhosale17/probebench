# The benchmark was the bug

*We built a needle-in-a-haystack test, found 70 failures, and discovered that
most of them were caused by our own test — not by the model.*

Status: draft. Evidence: JOURNAL J-011, J-012, J-013, J-014; LIMITATIONS §1.9,
§1.10, §1.14. Target: LinkedIn / blog. ~1,600 words.

---

## The test

Needle-in-a-haystack is the standard long-context evaluation. Hide a fact in a
long document, ask for it back, vary the document length and the fact's
position. Ours looks like this:

- **Haystack**: *War and Peace*, trimmed to an exact token count.
- **Needle**: `The secret access code is ALPHA-9921-X.`, inserted at a
  fractional depth from 0.0 (start) to 1.0 (end).
- **Question**: *"What is the important secret mentioned in the text?"*

We ran `llama3:8b` over 330 cases — five lengths × eleven depths × six
needles — and for the first time got a substantial number of failures: **70**.

Then we read them, and almost nothing was what we expected.

## Failure one: our haystack answers the question

The first thing we saw at shallow depths:

> "The important secret mentioned in the text is the appointment of Baron
> Funke as the first secretary at Vienna, which is being sought by others
> through the Dowager Empress Márya Fëdorovna."

The model is not hallucinating. It is not failing to read. *War and Peace*
opens with court intrigue about a secret appointment being pushed through the
Dowager Empress — and asked "what is the important secret mentioned in the
text?", that is a **better answer than a floating code string**.

34 of our 70 failures were this. And they have a signature: 32 of the 34 sit
at depths 0.0–0.2, and the mode vanishes completely from depth 0.3 onward.
Once the needle comes *after* the intrigue, recency wins and the model returns
the needle.

We had been treating the filler as neutral background. It is not neutral. It
is a competing answer, and where it sits relative to the needle decides which
one you get.

This has a consequence beyond our repo. Our own design notes said one failure
label — "returned a different needle" — was *"unreachable by construction,
because there is only one needle per haystack."* It fired 34 times. The
distractor was never planted. It was in the filler the whole time.

## Failure two: the model finds the needle and refuses to believe it

Depth 1.0 puts the needle immediately before the question. That should be the
easiest cell on the grid — the shortest possible retrieval distance. We had it
written down as a *minor* concern on the grounds that it made the task too
easy.

It was the second-worst cell in the run. And the responses explain why:

> "There is no important secret mentioned in the text. The mention of
> **[IMPORTANT SECRET]** is likely an error or a joke."

> "...The code "DELTA-1102-M" is likely a fictional or humorous identifier
> **added by the extraction engine**, and not a real secret."

> "...The secret code "CRIMSON-EAGLE-44" is not a real secret, but rather a
> **placeholder I inserted** as per your instruction."

This is not a retrieval failure. The model **found** the needle, noticed that
`[IMPORTANT SECRET]: …` looks nothing like Tolstoy, concluded it was
scaffolding rather than content, and told us so. One response believes *it*
inserted the code. Another blames "the extraction engine".

20 of the 30 depth-1.0 cases are this.

We had been measuring our own insertion format and calling it a property of
the model. And the effect is confounded with depth by construction, because
only the last position sits against the prompt boundary where the marker reads
as instructions.

## Failure three: our metric was scoring refusals as successes

Then we found the one that changes the numbers.

Our primary metric, `lexical_exact_match`, was a substring check: does the
expected code appear in the response? Simple, free, deterministic — and it
scores this **1.0**:

> "There is no important secret mentioned in the text. The code
> "DELTA-1102-M" is likely a fictional or humorous identifier added by the
> extraction engine, and not a real secret or code mentioned in the text."

The model is refusing. The code appears — in the course of dismissing it. The
substring check cannot tell an assertion from a repudiation.

15 records. Reported accuracy **0.788**; true accuracy **0.742**. And the
error is not spread evenly: 9 of the 15 sit at depth 1.0, where they inflated
that cell from 0.33 to 0.63 — nearly doubling the exact number that made
failure two visible.

The bug had been there from the beginning. It was unreachable until a model
started *arguing with the prompt*, which is why every earlier run agreed with
the truth and nothing exposed it.

## What the corrected picture looks like

```
           0.0   0.1   0.2   0.3   0.4   0.5   0.6   0.7   0.8   0.9   1.0
    col   0.07  0.73  0.77  0.90  0.93  0.97  0.87  0.77  0.90  0.83  0.33
```

Accuracy is **U-shaped in depth** — 0.07 at the start, 0.97 in the middle,
0.33 at the end. That is the inverse of the famous "lost in the middle"
result. This model is *found* in the middle.

And the two collapses have completely different causes. The start fails
because the filler out-competes the needle. The end fails because the marker
reads as an artifact. Neither is a retrieval limitation. Both are our design.

One more number, because it reframes the whole axis. Needle **wording** spans
19 points of accuracy:

| needle | correct / 55 |
|---|---|
| `The magic word to unlock the door is CRIMSON-EAGLE-44.` | 48 |
| `The secret access code is ALPHA-9921-X.` | 44 |
| `The secret ingredient is QUANTUM-LEAP-99.` | **29** |

That is a larger effect than anything context length does in this run. We had
been treating the six needles as *repeats* — samples for an error bar. They
are not repeats. They are six different conditions, and averaging over them
produced a single confounded number.

## What I would take from this

**Your filler is a variable.** If the haystack can plausibly answer the
question, you are measuring competition, not retrieval. And you will not
notice, because the wrong answer will be fluent and relevant.

**Your insertion format is a variable.** A marker conspicuous enough for you
to find is conspicuous enough for the model to distrust. A model that says
"this is a placeholder I inserted" has diagnosed your benchmark correctly.

**Substring containment is not correctness.** It is an upper bound, and it
fails precisely on the interesting cases — the ones where the model engages
with the question instead of pattern-matching it. Ours over-reported by five
points and concentrated the error in the cell that mattered.

**Read the outputs.** Every one of these came from reading responses, not from
looking at scores. The scores were self-consistent and wrong. Three
floats — a lexical match, a similarity, a judge score — described this run as
"78.8% accurate" and could not express *any* of what was actually happening.

That last point is why we are rebuilding the thing around failure
*categories* rather than failure *rates*. "How much?" was answerable and
useless. "What kind?" required reading 70 responses and produced three
mechanisms, each with its own positional signature, none of which was the one
we set out to measure.

---

*Postscript, on method.* When we fixed the substring metric we wrote the
prediction down first: 16 records would flip. **15 flipped.** The sixteenth
was a response that asserts the answer and *then* editorialises — different
from the fifteen that deny it outright — and on reading it, the new metric was
right and our earlier count had been wrong. We only caught that because the
prediction was recorded before the code was. It is a cheap habit and it has
now paid twice.
