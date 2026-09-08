# ProbeBench — Code Map

What every file does, how it does it, and **why it exists**. The third column
is the one that matters: a file's relevance is usually a limitation it closes
or an invariant it enforces, and that is not visible from the code alone.

Companion documents: [DESIGN.md](DESIGN.md) (architecture and mechanism),
[LIMITATIONS.md](LIMITATIONS.md), [JOURNAL.md](JOURNAL.md) (observations),
[DECISIONS.md](DECISIONS.md) (choices), [RESOLVED.md](RESOLVED.md) (fixes).

**Reading order for a newcomer:** this file → DESIGN.md §1–2 (the two
production failures that shaped everything) → LIMITATIONS.md §1 → run
`uv run probebench models inspect qwen3:4b` and `uv run probebench plan qwen3:4b`.

---

## The one-paragraph version

A run resolves its settings (`core/settings.py`), checks the machine can
afford the work (`core/preflight.py`), measures what machine and what serving
stack it is on (`core/hostinfo.py`, `core/kvprobe.py`), builds haystack cases
with a needle hidden at a known depth
(`benchmarks/long_range_dependency/NIAH/`), calls the model
(`models/ollama.py`), scores each answer on two axes — did it retrieve, did it obey —
(`evaluation/long_range_dependency/NIAH/`), and writes one JSON line per case
carrying the answer, the scores, and enough provenance to reproduce and join
it later (`core/result.py`, `reporting/jsonl.py`). `core/runner.py` is the
loop in the middle; `cli.py` is the front door.

---

## `core/` — provider-agnostic machinery

Nothing here may mention needles or haystacks. That scope rule is what lets a
second benchmark family reuse all of it.

| File | What it does | How | Why it exists |
|---|---|---|---|
| `config.py` | The typed run configuration | `RunConfig` composing `SweepConfig` / `ExecutionConfig` / `JudgeConfig` / `EmbeddingConfig` / `TokenizerConfig` dataclasses | One object carries everything a run needs, so provenance is recordable rather than scattered across function arguments |
| `settings.py` | Layers `probebench.toml`, env vars and CLI flags into that config | `tomllib` + pydantic with `extra="forbid"`; `[machine.*]` and `[experiment.*]` are **separate types** with non-overlapping keys | **D-016.** The needle marker and question wording are first-order variables (§1.9, J-012) and were hardcoded. The type-level split means a machine profile *cannot* change what is measured — §1.6 made structural instead of remembered |
| `case.py` | `BenchmarkCase` — one prompt plus its metadata | Small dataclass | The family-agnostic hand-off between a benchmark and the runner |
| `case_identity.py` | Hashes a case's identity | Canonical JSON (sorted keys) + SHA-256, with `FINGERPRINT_VERSION` stamped **inside** the digest; refuses raw floats | **D-012, invariant 11.** `case_id` shifts when the sweep changes (J-004), so results could not be joined across runs. Rejecting floats is not fussiness: `0.1+0.2` and `0.3` would hash differently |
| `runner.py` | Runs cases: `generate()` then `evaluate()` | Split into two phases so all generation happens before any judging | **Invariant 3 / R-002.** An interleaved judge evicts the generation model every case — a real production failure. Also enforces **invariant 1**: a failed evaluator leaves its metric ABSENT, never `0.0`. Since D-018 it also *records* the system prompt instead of discarding it — that string is the task statement, and a compliance rate against an unrecorded instruction is undefined (J-021) |
| `result.py` | `BenchmarkResult` and `to_record()` | Builds the nested JSON shape written to disk | The record *is* the research output. If a fact is not here it is unavailable later — which is why the archive's `llama3` runs can never be re-analysed |
| `schema.py` | `CURRENT_SCHEMA_VERSION`, currently `"1.4"` | Two constants | **Invariant 7.** The archive once had three record shapes all declaring `"1.0"` (J-005) |
| `migrations.py` | Upgrades old records to the current shape | A `(from, to)` map walked in a chain; each migration is a **pure function of the record** | Lets 426 archived records be read as one shape. Purity is enforced by test (D-015): a migration that read `needles.txt` would produce different keys depending on when it ran |
| `preflight.py` | Predicts whether a context fits in memory | The KV cache formula `2·layers·kv_heads·head_dim·bytes` against `MemAvailable + free VRAM` | **R-001, invariant 2.** The project's most novel piece. Derived from a real 36 GB allocation crash and reproduces it exactly |
| `kvprobe.py` | Measures the server's *actual* KV precision | Loads one model at two context sizes, differences `/api/ps` `size`; weights and buffers cancel | **D-017, J-018.** `--kv-cache-type` only fed the estimator and mislabelled records (J-016). The daemon runs as another user so its config is unreadable — so measure the behaviour instead |
| `hostinfo.py` | Records which machine ran the work | `/proc/cpuinfo`, `/proc/meminfo`, one `nvidia-smi` call; **`null` when Ollama is remote** | **D-013.** Latency was uninterpretable across three machines. Refusing to guess is the point: client specs on a remote run would look authoritative and be wrong |
| `health.py` | Pre-run environment checks | Daemon reachable, models present, data files present, disk writable | Fails in seconds instead of at case 300 |
| `retry.py` | Transient-failure backoff | `with_retries(...)` | 404 is retryable here — see DESIGN §2.2, a non-obvious call |
| `evaluator.py` | The `Evaluator` interface and `validate_score` | ABC + a range check | The range check is what caught the judge returning `100.0` (J-006). It refuses to guess rather than rescaling |
| `model.py` | `Model` / `ModelResponse` | Small dataclasses | Keeps `core/` from importing Ollama |
| `tokenizer.py`, `embedding.py` | Provider interfaces | ABCs | Same reason |
| `benchmark.py` | **Empty.** Placeholder for a `CaseGenerator` protocol | — | Intentional: benchmarks are duck-typed today. Listed so it is not mistaken for a deleted file |

## `benchmarks/long_range_dependency/NIAH/` — case construction

| File | What it does | Why it exists |
|---|---|---|
| `generator.py` | Builds one haystack: tokenize filler, splice the needle at `depth`, decode | The needle is inserted as `\n\n[IMPORTANT SECRET]: …\n\n`. **That marker is a measured variable, not scaffolding** — at depth 1.0 the model disputes it as an artifact (J-012). Also re-encodes the 3.3 MB corpus on every call, a known inefficiency |
| `benchmark.py` | Iterates the (length × depth × needle) grid; converts to `BenchmarkCase` | Where `num_ctx` gets bucketed to 512 tokens — a one-token difference spawns a second `llama-server` (R-002). Also where case identity is attached |
| `identity.py` | Builds `case_key` and `case_fingerprint` for NIAH | Two keys answer different questions: the grid *coordinate* (survives construction changes) and the *content address* (asserts identical bytes). D-012 |
| `settings.py` | Typed validation of NIAH's knobs | `NiahParams` defaults must equal the old hardcoded values **byte-for-byte**, or the whole archive stops joining. There is a test for exactly that |
| `schemas.py` | `NiahCase` | The benchmark-internal shape before conversion |

Data lives in `data/long_range_dependency/NIAH/`: `filler_text.txt` is *War
and Peace* (**not neutral** — its opening court intrigue is answered instead
of the needle 34 times, §1.9) and `needles.txt` holds six needles whose
wording spans **19 points** of accuracy.

## `evaluation/long_range_dependency/NIAH/` — scoring

| File | What it does | Why it exists |
|---|---|---|
| `lexical.py` | Does the response *assert* the expected answer? | Containment alone scored refusals 1.0 — a model quoting the code while calling it fake (J-013). Now containment **minus** a narrow repudiation guard (D-011). The guard only ever removes credit |
| `semantic.py` | Cosine similarity of response vs expected | **Dropped from NIAH (D-019), class retained.** J-022 found it was not a weak correctness metric but a near-perfect detector of response *form* — min 0.9918 bare vs max 0.7977 prose, zero overlap in 424 records. `compliance.py` decides the same thing exactly and offline. Kept for future prose-answer families |
| `judge/judge.py` | LLM-as-judge: a score plus a `grounded` label | One call answers two questions. `num_ctx` is **pinned** (invariant 3). `grounded` is a *label*, deliberately kept out of `metrics` so it cannot be averaged into a rate (D-010) |
| `judge/prompt.py` | The judge contract | Composed from sections so the scoring half exists once. Its earlier version asked for a percentage *then* a division, and the model skipped the division (J-006) |
| `compliance.py` | Did the response obey "answer ONLY with the code"? | **D-018.** 85% of the archive did not, and `qwen3:4b` obeys 37/37 while `llama3:8b` obeys 0/330. Scores **form**, never the expected value — matching on `expected` would make compliance imply retrieval and collapse the 2×2 (J-022). Carries `RULE_VERSION` from birth, which is the one thing `lexical_exact_match` cannot do (D-014) |

## `models/` — the Ollama backend

| File | What it does | Why it exists |
|---|---|---|
| `ollama.py` | Calls the model; captures the evidence | Keeps `done_reason`, `prompt_eval_count`, `eval_count`, server-side timings and `thinking_chars`. `prompt_eval_count` is the **only measured x-axis** we have (§1.1). `think=False` is a trap on qwen3:4b — it leaks the chain of thought into `content` (J-017) |
| `registry.py` | Reads GGUF metadata | Extracts layers, KV heads, head dim — the KV formula's inputs. Uses a **suffix matcher** because keys are architecture-prefixed (`qwen3.block_count`); a literal key would silently fall back and the memory guard would stop guarding |
| `installer.py` | Pulls missing models, with confirmation | **Invariant 6** — a multi-gigabyte download is never implicit |
| `host.py` | Resolves the Ollama endpoint | Normalises `OLLAMA_HOST`, which is commonly written without a scheme |
| `ollama_embeddings.py`, `embedding_factory.py` | Embedding provider | Batched so expected and predicted go over the wire together |

## `experiments/` — orchestration

| File | What it does | Why it exists |
|---|---|---|
| `registry.py` | `ExperimentSpec` registry | Adding an experiment should require **no edits elsewhere** — the CLI, `all`, and the health check all read from here |
| `long_range_dependency/NIAH/run.py` | Wires everything into one run | The order matters: settings → host → KV probe → cases → memory plan → generate → evaluate → write. The probe runs *before* generation so it cannot evict the sweep's runner |

## `reporting/`

| File | Status | Why |
|---|---|---|
| `jsonl.py` | **live** | The only consumer today. One JSON line per case |
| `markdown.py`, `csv.py`, `json.py` | **dead code** (§5.1) | Never called. `markdown.py` already contains a context × depth pivot worth resurrecting rather than rewriting |

## `cli.py`

The front door. Notable: `probebench <model>` is rewritten to
`probebench all <model>`; `--context` is a **CEILING that drops oversized
cases, not a resize** (invariant 4); every measured option defaults to `None`
so the config file can supply it (D-016 — argparse cannot otherwise tell "the
user asked for the default" from "the user did not ask").

## Tests

| File | Guards |
|---|---|
| `tests/core/test_migrations.py` | Every archived record migrates; the chain walk; migrations stay pure functions |
| `tests/core/test_case_identity.py` | Fingerprints are order-stable, reject floats, change with every component, and **ignore hardware** |
| `tests/core/test_settings.py` | Typos raise; a machine section cannot carry a measured key |
| `tests/core/test_kvprobe.py` | The probe recovers f16/q8_0 and is weight-independent |
| `tests/benchmarks/test_niah_params.py` | Config defaults equal the old hardcoded values — the archive's join depends on it |
| `tests/evaluation/test_lexical.py` | The 15 known repudiations score 0.0; the J-014 borderline case scores 1.0 |
| `tests/evaluation/test_compliance.py` | A **bare but wrong** answer still scores 1.0 — if that ever fails, the rule has collapsed into `lexical_exact_match` and the 2×2 is gone |

## Outputs

`results/raw/<family>_<experiment>_<model>_<run_id>.jsonl` — one line per
case. Git-ignored. **The `.log` sidecars were removed on 2026-09-07**: nothing
read them, and the one thing they uniquely held — skipped cases — is a
recording gap now tracked as §4.7 rather than a reason to keep untracked
files (J-019).
