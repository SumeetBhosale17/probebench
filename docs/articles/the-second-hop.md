# The second hop

*We spent weeks building a benchmark that couldn't fail. Then we changed one
sentence and it failed 32% of the time — at the easiest setting in the grid.*

---

## The problem with a perfect score

Needle-in-a-haystack is the standard long-context test. Hide a fact in a pile of
filler text, ask the model to find it, vary the pile's size and the fact's
position, plot accuracy.

Our version worked. That was the problem.

Across 590 archived result records, every metric on a successful case was
`1.0`. Not "high" — exactly 1.0. Retrieval accuracy, judge score, everything.
`qwen3:4b` found the needle at 4,000 tokens, at 32,000 tokens, at the beginning,
at the end. So did the small models. We had built an instrument with no
dynamic range.

This matters more than it sounds. The whole point of the project is to
*diagnose* failures — to say **what kind** of wrong an answer is, not just how
wrong. We had a taxonomy of failure modes designed and ready to implement, and
no failures to test it against. A classifier that never fires is
indistinguishable from a classifier that is correct.

You cannot validate a theory of failure on a dataset with no failures.

## Changing one sentence

The fix was not a longer context or a weaker model. Both of those make the task
*harder*; neither makes it **different**.

Instead we changed what the planted fact says. The original:

```
[IMPORTANT SECRET]: The secret access code is ALPHA-9921-X.
```

The replacement — a pointer, plus a registry of codes scattered elsewhere in
the same document:

```
[IMPORTANT SECRET]: The access code for Redmont is the same as the
                    access code for Brightwater.

...  ~1,500 tokens of Tolstoy  ...

[IMPORTANT SECRET]: The access code for Brightwater is TRV-4417-QD.

...  more Tolstoy, more registry entries  ...
```

Question: **What is the access code for Redmont?**

The answer is `TRV-4417-QD`, and it is *right there in the text*. Nothing is
hidden, nothing is ambiguous, nothing is longer than before. The only change is
that finding it requires two lookups instead of one: read the pointer, learn it
means Brightwater, then find Brightwater's entry.

The first run was six cases at 4,000 tokens — the shortest, easiest setting we
have, the one where the original benchmark had never once been wrong.

Two of the six failed.

## What the failures looked like

```
expected: TRV-4417-QD
returned: "The access code for **Redmont** is not explicitly mentioned in
           the provided text. However, based on the information give..."

expected: MKP-8823-LN
returned: "None of the access codes listed in the text relate to Redmont."
```

Both responses are *confident*, *fluent*, and *wrong in the same specific way*.
The model found the pointer — it knows Redmont is the thing being asked about.
It searched the registry for a Redmont entry. There isn't one, because that is
the entire design. And it concluded the answer does not exist.

It resolved the pointer's **subject** and never its **referent**. The second hop
was never taken.

That is not a retrieval failure. Every fact needed was present and findable; the
model found some of them. It is a *composition* failure, and it is a category
our benchmark had been structurally incapable of producing.

## Why we could say that without reading the text

Here is the part that generalises, and it has nothing to do with long context.

**We built the haystack, so we know exactly what is in it.** Since a recent
schema change, every result record carries the full inventory of what was
planted — every value, its role, its subject, the order it appears in, the token
offset it landed at:

```json
"needle_inventory": [
  {"role": "distractor", "subject": "Brightwater", "value": "TRV-4417-QD",
   "document_index": 0, "token_offset": 731, "realised_depth": 0.1825},
  {"role": "target",     "subject": "Ashford",     "value": "MKP-8823-LN",
   "document_index": 1, "token_offset": 1726, "realised_depth": 0.4313},
  {"role": "pointer",    "subject": "Redmont",     "value": "",
   "document_index": 2, "token_offset": 1990, "realised_depth": 0.4973}
]
```

With that on disk, classifying a failure is a regex and a dictionary lookup. Did
the response contain a code? Was that code one we planted? Which block was it
in, and where did that block sit relative to the right one?

No second model call. No LLM-as-judge. No human reading 100 responses. And —
critically — **it can be re-run over stored results without re-running the
models**, which is what makes iterating on the classification rules affordable
at all.

Synthetic benchmarks should exploit this and mostly don't. If you generated the
input, you have ground truth about its *structure*, not just its answer. Storing
only the expected answer throws that away.

## Then we ran fifty

Six cases is not a sample. We ran the grid properly — five pointer depths, three
registry sizes, the hop swept across the registry. Fifty cases.

**Sixteen failures**, in two distinct modes:

```
 9  no code emitted           ("None of the access codes for Redmont
                                is mentioned in the provided text.")
 7  returned a planted code   — but the wrong one
```

And the first thing the larger run did was **prove a claim we had written down
four hours earlier wrong.**

At n=6, zero failures had returned a wrong-but-planted code. We had noted that
as evidence: the failure label we'd built the whole distractor machinery for
wasn't what real failures looked like. At n=50 it fires seven times out of
sixteen.

The observation at n=6 was accurate. The inference from it was not. We keep both
— the journal is append-only, so the entry that was wrong stays exactly as
written, and a later entry says why. An entry whose conclusion the data
overturned is the most useful kind, because it records what six cases *looked
like* they were saying.

## The effect nobody predicted

We expected failures to track how deep the pointer was buried, and how many
decoys competed with it. Depth behaved:

```
pointer depth   failures
    0.1         6/10  (60%)
    0.3         4/10  (40%)
    0.5         2/10  (20%)
    0.7         1/10  (10%)
    0.9         3/10  (30%)
```

But the biggest effect in the run was something we hadn't thought to look for:
**which entry in the registry the pointer names.**

```
hop            k   rank  document position   failures
Brightwater    8   0     0.0595              0/5   (0%)
Ashford        8   1     0.1893              2/5  (40%)
Kingsley       8   2     0.3137              4/5  (80%)
Stonegate      8   3     0.4380              0/5   (0%)
Kingsley       4   2     0.6853              4/5  (80%)
```

Look at the last two rows. Kingsley fails 80% of the time at registry size 4 and
80% at registry size 8 — at document positions of 0.685 and 0.314. Same **rank**
in the registry, completely different **place** in the text, identical failure
rate.

So it is not about where the answer sits. It is about which registry entry it is.

And here is where an honest writeup has to stop. Our registry is built in file
order, so rank 2 is *always* Kingsley. Three explanations fit the data equally
well and it cannot distinguish them:

1. a middle-of-registry effect — ranks 0 and 3 are endpoints, and both are easy,
   which is what primacy plus recency looks like;
2. something about the token `Kingsley` specifically;
3. something about its code `ZBF-2094-HW`, the only planted value starting
   with Z.

Separating them means permuting the registry order so rank and identity vary
independently. That is a small change and it is the next run. Until it happens,
the finding is "there is a large rank-or-identity effect", not "position in a
list predicts failure".

We also nearly reported an off-by-one. Five of the seven wrong-code answers
returned the entry immediately adjacent to the right one, and Kingsley→Stonegate
accounted for three. It looks like a law. It isn't: with four registry entries,
two of the three wrong choices *are* adjacent, so chance alone predicts about
two-thirds adjacency. Five out of seven is unremarkable. The pattern went into
the record explicitly labelled as not-a-finding, so nobody rediscovers it in six
months and gets excited.

## What this cost

One sentence in a template, one extra block in the haystack, and roughly a day.

The infrastructure to *interpret* the result — content-addressed case identity,
a versioned schema, the recorded inventory — took considerably longer and looked
like pure overhead the entire time it was being built. It stopped looking like
overhead the moment there was something to diagnose.

Three things to take away:

**A benchmark that saturates is not measuring your model.** It is measuring the
ceiling you built. Before making the task harder, ask whether you can make it
*different* — our failures came from changing the task's structure, not its
size, and they appeared at the setting we had already declared trivially easy.

**Record what you constructed, not just what you expected.** The answer key tells
you *whether* a response was wrong. The construction log tells you *how* — and
lets you re-derive that judgement offline, months later, without paying for
inference again.

**Six cases is not a sample.** We wrote a conclusion from six cases and the same
day watched fifty overturn it. The fix is not to be more careful with small
samples; it is to write down what you believed, so that being wrong is
recoverable rather than invisible.

---

*ProbeBench is a research framework for diagnosing long-context LLM failures
rather than scoring them. The runs described here are `qwen3:0.6b` at 4,000
tokens; the rank effect is confounded with subject identity, the length sweep
has not been run, and neither result has been replicated on a second model.*
