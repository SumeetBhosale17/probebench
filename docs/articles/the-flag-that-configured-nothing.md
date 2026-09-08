# The flag that configured nothing

*How a one-line benchmark option quietly lied about every run it touched — and
how we ended up measuring the thing instead of asking about it.*

Status: draft. Evidence: JOURNAL J-016, J-018; DECISIONS D-017.
Target: LinkedIn / blog. ~1,400 words.

---

## The setup

We are building ProbeBench, a framework for diagnosing *why* language models
fail on long inputs rather than just scoring them. Long context costs memory,
and the dominant cost is the KV cache — the keys and values a transformer
keeps for every token it has already seen. It is linear in context length:

```
kv_bytes_per_token = 2 · n_layers · n_kv_heads · head_dim · bytes_per_element
```

For a 4B model that is 144 KiB per token. At 262,144 tokens — the context this
model advertises — that is **36 GB of cache alone**, which is how we crashed a
laptop and got interested in this in the first place.

One obvious lever is the last term. Store the cache at 8 bits instead of 16
and the whole thing halves. Ollama exposes that as `OLLAMA_KV_CACHE_TYPE`, so
we added a flag:

```bash
probebench qwen3:4b --kv-cache-type q8_0
```

We wanted to ask a research question with it: **does quantising the KV cache
hurt retrieval accuracy?** It is a good question. Nobody has a clean answer at
small scale, and it decides whether every later experiment gets twice the
context budget for free.

## The problem

Before running it, I went looking for where the flag actually took effect.

```
$ grep -rn "KV_CACHE_TYPE" src/
src/probebench/cli.py:149:  "...assumed when estimating memory. Set OLLAMA_KV_CACHE_TYPE to match."
src/.../run.py:295:        "  - set OLLAMA_FLASH_ATTENTION=1 and OLLAMA_KV_CACHE_TYPE=q8_0, "
```

A help string and a printed hint. That is all.

The flag's only real consumer was one line:

```python
kv_cache_bytes_per_element = 1 if args.kv_cache_type == "q8_0" else 2
```

…which feeds the *memory estimator*. It changes what we predict a run will
cost. It does not change what the run does.

And then that assumption gets written into every result record, in a field
called `kv_cache_bytes_per_element`, sitting in a block called `generation`,
right beside genuine facts about the run.

So a run invoked with `--kv-cache-type q8_0`, against a server nobody had
reconfigured, would **generate at f16 and archive a record saying `1`**. Not a
crash. Not a warning. A confidently mislabelled row, indistinguishable from a
real one, in a dataset we intended to publish from.

The experiment would have "worked". Both arms would have been f16. We would
have measured noise and reported it as "KV quantisation has no effect."

## The obvious fix, and why it was wrong

The obvious fix is to read the environment variable and cross-check it against
the flag. I wrote that down as the plan.

Then I checked how Ollama actually runs:

```
$ systemctl is-active ollama
active
$ ps -o pid,user,cmd -C ollama
    922 ollama   /usr/bin/ollama serve
$ cat /proc/922/environ
cat: /proc/922/environ: Permission denied
```

Ollama is a **systemd service running as its own user**. Our shell's
environment is a different process's environment. Setting
`OLLAMA_KV_CACHE_TYPE` in our terminal changes nothing about the server.
Reading it tells us nothing about the server. And the server's own environment
is not readable without root.

This is the default install on Arch, Ubuntu and macOS. So the "obvious fix"
would have been correct only in the narrow case where you personally launched
`ollama serve` in the same terminal — and would have produced a
confident-looking, checkable-looking field that was unrelated to the run
everywhere else.

That is worse than recording nothing. A missing field makes you go and look. A
wrong field makes you stop looking.

## Measuring instead of asking

Here is the part I did not expect to work.

Ollama's `/api/ps` endpoint reports every loaded model's resident `size` — and
the `context_length` it was loaded at. And resident size is:

```
size(ctx) = weights + compute_buffers + kv_bytes_per_token · ctx
```

Only the last term depends on context. So load the *same model twice at two
different context sizes* and subtract. Weights cancel. Buffers cancel. What is
left is the KV cache, and dividing by the geometry we already read from the
model's metadata gives the one unknown:

```
qwen3:0.6b — 28 layers, 8 KV heads, head_dim 128

size @  4,096 = 1,034,975,968 bytes
size @ 16,384 = 2,396,321,218 bytes
                ────────────────────
delta         = 1,361,345,250 bytes over 12,288 tokens
              = 110,787 bytes/token

bytes_per_element = 110,787 / (2 × 28 × 8 × 128) = 1.93
```

**1.93 against a true f16 value of 2.0.**

No environment variables. No root. No assumptions about how the daemon was
started or who started it. It works against a service, and it works against a
machine on the other side of the network — because it only ever makes API
calls.

The nice part is what it reuses. We already had that formula, derived from a
crash, used to *predict* which contexts would fit. Turning it around and using
it as a **measuring instrument** was free. It was already there; we had only
been reading it in one direction.

## What we shipped

A run now measures its own serving stack at startup and records four separate
things, because "what we asked for", "what is true", and "how well we know"
are three different questions and collapsing them is exactly the defect we
were fixing:

```json
"kv_cache_type_requested": "q8_0",
"kv_cache_bytes_per_element_measured": 1.93,
"kv_cache_type_effective": "f16",
"kv_cache_probe": "measured"
```

And when they disagree, the run refuses to start:

```
RuntimeError: KV cache precision mismatch: --kv-cache-type says 'q8_0' but the
server is running 'f16' (1.932 bytes/element). ProbeBench cannot change a
running daemon's KV precision — set OLLAMA_KV_CACHE_TYPE on the OLLAMA SERVICE
and restart it, or drop the flag.
```

The mislabelled record is now unreachable. You cannot produce one.

## The honest caveat

Two consecutive probes of the same unchanged server gave **1.932** and
**2.080**. A 7% spread. The reported `size` at a fixed context moves between
loads, apparently with how much of the model happens to be resident in VRAM.

That is fine for the job — f16 and q8_0 are 2× apart, so a 7% wobble never
threatens the decision — but it does bound what this instrument can do. It
tells you which of three regimes you are in. It is not a precise measurement
of cache overhead, and we do not quote it as one. We record the raw evidence
so the number can be re-checked later without re-running anything.

## The payoff, three days later

We reconfigured the daemon for `q8_0` and restarted it. The probe said f16 —
and reported byte counts *identical* to the previous measurement, which is not
something a real precision change can do.

```
$ systemctl show ollama -p Environment
Environment=HOME=/var/lib/ollama OLLAMA_MODELS=/var/lib/ollama

$ cat /etc/systemd/system/ollama.service.d/override.conf
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_FLASH_ATTENTTION=1
```

Two faults in four lines. The drop-in has no `[Service]` header and no
`Environment=` prefix, so systemd ignored both lines. And `ATTENTTION` has a
doubled T, so even fixed it would export a variable nothing reads — and `q8_0`
KV needs flash attention, so the cache would have stayed f16 for a second
reason.

The service restarted cleanly. Nothing reported an error. Every alternative
design misses this: trusting the flag archives records labelled `q8_0` that ran
at f16; reading our own environment finds it empty because we never set it;
reading the daemon's `/proc/<pid>/environ` is permission-denied. Only measuring
what the daemon actually did with memory caught it.

That is the argument for measurement over configuration, made by the thing
rather than by me.

## The generalisable bit

Three things I would take to any project:

**A flag is a claim, not a fact.** `--kv-cache-type q8_0` was a statement of
intent. Somewhere between intent and the GPU it stopped being true, and
nothing noticed because the field it wrote was named after the intent.

**Separate what you asked for from what happened.** One field carrying both
meanings will drift, and when it does it looks exactly like a field that has
not drifted. Two fields cost nothing.

**When you cannot inspect a configuration, try measuring its consequences.**
We could not read the daemon's environment. We could watch what the daemon
*did* with memory, and the arithmetic connecting the two was already sitting
in the repo, being used for something else.

The bug was one line. The interesting part was that fixing it correctly
required giving up on asking the system what it was configured to do, and
measuring what it was actually doing instead.
