# ProbeBench — Competition Presentation and Panel Q&A Guide

**Prepared:** 2026-09-30  
**Audience:** technically strong evaluators, especially local/self-hosted LLM users  
**Purpose:** a defensible presentation narrative, accurate results, and prepared answers—not a claim that the research plan in the attached PDF is already complete.

> **Most important advice:** present ProbeBench as a diagnostic instrument and an honest engineering/research prototype. Do not present the planned Llama-versus-Mistral study, 500-probe protocol, validated taxonomy, fixed-seed llama.cpp runs, or cross-model failure-overlap statistics as completed work. Those statements appear in the presentation PDF but are not supported by the current implementation/archive. Explain the gap plainly; technical judges will respect an accurate boundary more than an inflated claim.

## 1. Project in one sentence

**ProbeBench is an experimental harness for testing how locally served language models retrieve and use facts in long text, while preserving enough case-level evidence and serving/memory provenance to investigate what went wrong—not just produce a leaderboard score.**

### A 20-second version

> “A model’s advertised context window is not the same as the context a person’s computer can actually run, and a single accuracy score does not explain a failure. ProbeBench builds controlled long-text retrieval and reasoning cases, checks memory feasibility before inference, records each response and its context, and scores it with explicit evaluators. The current archive already shows why evaluation design matters: a two-hop task exposed failures at only about 4,000 tokens where the basic retrieval task often looked saturated.”

### A 60-second version

> “ProbeBench asks a more useful question than ‘which model scored higher?’: under a known prompt and a recorded local serving setup, where does a model stop retrieving or composing information, and what does its response look like? It generates three distinct probe types: a single hidden fact, a hidden fact among look-alike decoys, and a two-hop pointer-to-registry task. It stores one structured result per case and has a memory preflight based on the model’s KV-cache geometry, because an advertised context length says nothing about whether a specific host can allocate the cache. In the current archived runs, the most informative result is not a universal ranking: qwen3:0.6b failed 16 of 50 cases in one 4K multi-hop sweep—nine with no code and seven with a wrong planted code. That is a useful failure signal, but it is still one model/task/context corpus, not a broad claim about models. The next step is controlled replication, human labels, and validating the failure taxonomy.”

## 2. What exists now versus what the PDF proposes

Treat this as the presentation’s scope contract. The PDF is a proposal/vision in several places; the repository and JSONL archive are the evidence for what is implemented and observed.

| Topic | What the attached PDF says or implies | What is supported by the current project | How to say it accurately |
|---|---|---|---|
| Models | Llama-2-7B versus Mistral-7B | The 33 archived runs include `llama3.2:1b`, `llama3:8b`, `qwen3:0.6b`, and `qwen3:4b`. No Llama-2-7B/Mistral-7B comparison is in this archive. | “The PDF described the intended architecture comparison; the current implementation’s archived models are these four Ollama tags. This is not an architecture-isolation experiment.” |
| Serving stack | llama.cpp, Q4_K_M, fixed seed, temperature 0 | The implemented backend is Ollama. There is no seed-control feature. Generation settings can inherit model/Modelfile defaults. | “The current experiment is Ollama-based, and this archive is not bit-reproducible. Pinning seed/temperature and broadening backend support remain future work.” |
| Probe count/design | About 500 probes, five dependency-distance bins | The archive currently loads 870 records from 33 runs. The probe families use context size and placement/depth grids, plus decoy count or registry size. 870 records are not 870 unique paired probes. | “We have 870 archived case records; the count includes different runs and experiment designs. The current axes are context length/needle position and task structure, not the PDF’s completed five-bin study.” |
| Human solvability | Human solvability check in methodology | No completed human-solvability audit is evidenced in the current artifacts examined. | Do not claim it has been run. Say it is needed to strengthen the task-validity argument. |
| Failure taxonomy | Structured mutually exclusive classes | A closed taxonomy/classifier is still planned. There are deterministic evaluators and recorded evidence, but not a validated general failure classifier with hand-labelled precision/recall. | “The observed failure modes motivate a taxonomy; the taxonomy is not yet validated or shipped as the classifier described in the PDF.” |
| Annotator agreement | Cohen’s κ | No annotator study or κ result is present in the current archive. | “That is an evaluation planned for the next phase, after collecting and double-labelling a failure corpus.” |
| Cross-model failure overlap | Jaccard index | Content-addressed case identity exists for newer records, but a controlled cross-model overlap result is not established by the current dashboard summary. Many legacy rows lack fingerprints. | “The framework is being prepared for valid joins; we do not yet present a defensible Jaccard comparison.” |
| Results claim | Failure curves and model divergence | The archive contains interesting results, including a 16/50 multi-hop failure run, but the runs are imbalanced, not uniformly replicated, and have known measurement caveats. | Present the multi-hop observation as a case study and research lead, not a general performance law. |
| Dashboard | A reusable explorer/result dashboard | A Streamlit dashboard and a static HTML report generator exist. The dashboard is useful for exploration but pools historical data and is not yet an inferential/statistical report. | “The dashboard is an exploratory viewer for the archive. Its headline KPI is not a paper-grade estimator.” |

## 3. The problem and why a self-hosting audience should care

Local users often see a model card claiming a large context window and assume it is a practical capacity guarantee. It is not. At inference time, memory is consumed by model weights, the KV cache, and implementation/runtime overhead. The KV cache grows linearly with context and depends on architecture and cache precision.

For a standard transformer KV cache, the project uses:

$$
\text{KV bytes/token} = 2 \times n_{layers} \times n_{KV\ heads} \times d_{head} \times bytes_{element}
$$

The leading factor of 2 accounts for keys and values. For the documented `qwen3:4b` geometry (36 layers, 8 KV heads, head dimension 128, f16 cache), this is 147,456 bytes per token, or 144 KiB/token. At 256,000 tokens the estimate is 36,000 MiB—matching the logged allocation failure. A 14-GiB-free host cannot satisfy that request just because the model advertises a 262,144-token window.

**The practical message:** “context supported by the model” and “context feasible on this machine with this serving configuration” are different claims. ProbeBench’s `plan`/preflight capability is designed to estimate the second before spending time loading a model or risking a runner failure. It is a feasibility estimate, not an exact prediction of total process memory: compute buffers, fragmentation, changing host contention, and GPU/runtime differences remain.

For a local user, the useful outputs are therefore not only accuracy:

- Which prompt/case was sent, and what answer came back?
- What context size was requested, and what did the model/server report as prompt tokens?
- Did the generation or evaluator fail, and was the metric absent rather than fabricated as zero?
- What model, tokenizer setting, judge, KV precision, and host information were recorded?
- Did the task test simple retrieval, discrimination among decoys, or composition across hops?

## 4. Explain the three experiments simply

Use a single diagram or three columns. Always say the arms test **different tasks** and cannot be collapsed into one difficulty ladder.

### A. Single needle — “Can it retrieve one planted fact?”

A target fact is inserted in a long text at a controlled position. The model is instructed to return the fact. The experiment varies target context length and needle depth. This is the familiar Needle-in-a-Haystack (NIAH) probe. It is useful as a controlled retrieval probe, but a highly templated/synthetic task can be easy and does not represent every kind of long-document use.

### B. Distractor — “Can it choose the requested fact among similar codes?”

A keyed set includes a target and decoy facts. The asked-for subject identifies which code is correct. Correctness is not merely “did it repeat any code?” The experiment varies the number of decoys. This is a discrimination task and changes the task relative to single-needle NIAH, so its score should not be pooled with NIAH as though only context length changed.

### C. Multi-hop — “Can it follow a pointer and then retrieve its referent?”

A pointer statement names a subject/location; a registry elsewhere maps subjects to codes. The pointer itself does not include the code. The model must locate the pointer, resolve the subject, then retrieve that subject’s value. This tests composition of two lookups, not just longer single-hop retrieval. Registry size is a task-difficulty factor; the task is not comparable to NIAH or the distractor arm.

### Analogy for non-specialists

- Single needle: find the one phone number hidden in a folder.
- Distractor: find the number belonging to the named person among several similar-looking numbers.
- Multi-hop: read “the key for the room assigned to Maya,” find Maya’s room, then find that room’s key.

## 5. How to present the results without overstating them

### Archive snapshot (dashboard loader, as of 2026-09-30)

The current results folder, as loaded by the dashboard’s shared data preparation, contains:

- **870 case records** across **33 runs**.
- **Four model tags:** `llama3.2:1b`, `llama3:8b`, `qwen3:0.6b`, and `qwen3:4b`.
- **Three experiment families:** NIAH, NIAH_distractor, and NIAH_multihop.
- **470 records with fingerprints and 400 without.** Legacy records cannot be retroactively given a real content fingerprint when the original prompt was not archived.
- **443 records marked self-judged** (judge and generation model match). Those `llm_judge` scores are not reportable as independent evaluation.
- **One record with non-`ok` status** according to loader coverage. That single status count does not mean every evaluator succeeded or that all metric fields exist.

The dashboard’s default selected metric is its `primary_acc` fallback: it takes `lexical_exact_match` when present, otherwise legacy `lexical`, otherwise `llm_judge`. Therefore, the headline **88% average** and “best model” card are descriptive output of a mixed historical archive and a compatibility fallback—not a clean, single-metric estimate of model capability. The archive also mixes task types and unequal run sizes. Do not use this headline as the principal result in a competition claim.

### A more defensible result to lead with

> “In one archived `NIAH_multihop` run, `qwen3:0.6b` answered 34 of 50 cases correctly at roughly 4K target context; 16 failed. Looking at the stored case inventory and responses, nine failures emitted no code and seven returned a planted but wrong code. This is evidence that a two-hop structure can expose failure modes hidden by simple single-needle retrieval. It is not evidence that all small models fail this way, that 4K is a general threshold, or that a taxonomy has been validated.”

Why this is the strongest story:

1. It states a task, model, sample size, and context.
2. It separates two observable failure shapes, rather than inventing a single vague “reasoning score.”
3. The planted inventory lets the response be checked against what was actually present, without asking another model to decide which distractor was returned.
4. It is bounded: one model, one run/corpus, no broad replication, and no human-labelled precision/recall yet.

The larger archive snapshot has additional patterns, but comparisons are not matched. For example, the pooled NIAH records vary greatly in sample size and contexts by model: `llama3:8b` has 385 NIAH cases around 4K–8K; `qwen3:0.6b` has 164 across roughly 4K–40K; `qwen3:4b` has 49 mostly at 4K with a few higher points; `llama3.2:1b` has only 6 around 128K. Those cannot support a simple model ranking or causal explanation.

### Distractor observation: disclose sample size

The current archive has distractor runs at decoy counts `k ∈ {0,1,2,4,8}` for `qwen3:4b`, with 12 records per count and all scoring as correct under the dashboard’s primary metric. That is an encouraging initial run, not evidence that performance is insensitive to decoys: it is only 12 cases per level for one model and does not supply a replicated uncertainty estimate. `qwen3:0.6b` has only 2 nonzero-decoy cases per count in the loaded archive; do not infer a trend from those cells.

### Avoid these result phrasings

- **Do not say:** “qwen3:4b is the best model.”  
  **Say:** “It is 100% on the cases in this particular archive slice; those cases are not a matched benchmark comparison, and the dashboard’s pooled ranking is not a general model ranking.”
- **Do not say:** “Accuracy drops as context increases” as a universal conclusion from the dashboard.  
  **Say:** “Some individual runs show degradation; context, model, task, wording, corpus, and run design are not balanced across this archive.”
- **Do not say:** “The model failed at 4K.”  
  **Say:** “The observed multi-hop failures occurred in a 4K target-context experiment; that is not a universal context-capacity boundary.”
- **Do not call all 870 rows independent samples.** They include repeated/related configurations and different runs; the sample unit and repeated structure matter.
- **Do not call the dashboard’s 88% the project’s benchmark score.** It is an exploratory pooled average.
- **Do not call the judge an independent ground truth.** Hundreds of cases are self-judged, and even an independent LLM judge is not human ground truth.

## 6. Suggested 8–10 minute presentation

Adapt the slide count to the competition format. The wording below is speaker-ready; reduce it rather than adding unsupported claims.

### Slide 1 — Title and hook (45 seconds)

**Title:** “ProbeBench: Diagnosing Where Local LLMs Fail in Long Contexts”

**Say:**
> “If a model advertises 256K context, can my local machine actually run that experiment—and if the answer is wrong, can I tell whether it lost the fact, chose a distractor, or failed to follow a chain of references? ProbeBench is built to make those questions measurable.”

Use the actual project title only if it does not imply that the planned cross-architecture comparison is already complete. Avoid making the title a claim about architecture-specific causal diagnosis.

### Slide 2 — The gap (60 seconds)

One overall score hides the input, the answer, the failure type, and the serving conditions. Self-hosting also creates a practical constraint: the memory budget can be reached well before the model’s advertised token maximum.

**Say:**
> “A leaderboard tells me who scored more on a benchmark. It usually does not tell a local user what context fit their machine or what kind of failure happened on a particular prompt. Our goal is to preserve the case-level evidence needed to ask those follow-up questions.”

Do not claim that aggregate benchmarks are useless. Say they answer a different question and are insufficient for this diagnosis.

### Slide 3 — What is controlled (60 seconds)

Show a sample context with a marked target and query, then identify the varied factors: requested target length, target position, decoy count, and registry size/task structure.

**Say:**
> “We generate cases from known ingredients, so we know which facts and codes are present. We then vary selected factors. The three experiment arms change the task itself: retrieval, discrimination, and two-hop resolution. They are separate experiments, not points on one shared scale.”

### Slide 4 — Local serving and memory feasibility (75 seconds)

Show the KV formula and one concrete arithmetic example. State the actual stack is Ollama. Mention that the preflight estimates weight + KV + safety buffer against available host memory; it is not a guarantee against all runtime allocation conditions.

**Say:**
> “The model’s maximum context is an architectural limit, not a host-feasibility guarantee. For qwen3:4b’s documented geometry, f16 KV uses about 144 KiB per token. At 256K tokens that is 36,000 MiB, which matches a real allocation error we observed. ProbeBench turns that incident into a pre-run estimate. The estimate still has residuals—compute buffers, fragmentation, and changing memory pressure—so it is a guard and planning model, not an exact total-memory oracle.”

### Slide 5 — Measurement and result record (60 seconds)

Show one JSONL record/architecture flow: config → preflight → cases → generation → evaluation → JSONL. Explain that a failed evaluator leaves its metric absent rather than assigning zero, and every case can retain provenance/status/evaluator information. Keep implementation details to one diagram.

**Say:**
> “The result is not just a float. It is one record per case. A missing judge score remains missing; it is not silently converted into a zero. This matters because failed evaluation and incorrect model output are different events.”

### Slide 6 — The finding (90 seconds)

Lead with the 50-case qwen3:0.6b multi-hop run: 34 correct / 16 failures; among failures, 9 emitted no code and 7 emitted a different planted code. If showing the dashboard, immediately state it is an exploratory view and do **not** use its pooled KPI as the conclusion.

**Say:**
> “The most interesting signal is task structure. At a roughly 4K target context, the single-hop baseline can look easy, while the two-hop run produced 16 failures out of 50. Nine gave no code; seven returned a code that was present, but belonged to the wrong registry entry. Knowing the entire planted inventory lets us distinguish those two behaviors. It suggests a useful diagnostic probe; it does not yet establish prevalence or generalize to other models.”

### Slide 7 — What is not yet proven (60–75 seconds)

Use three or four honest constraints: tokenizer mismatch; small/unbalanced samples/no seed; self-judging; no hand-labelled taxonomy validation; no matched causal architecture study. This is not an apology—it demonstrates research literacy.

**Say:**
> “We are not claiming a validated taxonomy or a causal architecture result. The current system has useful instrumentation and an initial failure corpus, but context counts are cl100k-equivalent rather than model-native; several runs are self-judged; repeated trials and seed control are missing; and we have not measured classifier precision/recall against human labels. Our next experiment is designed around those gaps.”

### Slide 8 — Why the contribution matters / next milestone (45 seconds)

Frame contribution as a system and a method: memory-aware local preflight, controlled synthetic tasks, one record per case with evidence/provenance, and a concrete distinction between simple retrieval and composed lookup. Next: matched designs, repeats/seeds, human annotation, then validation of rules and cross-model joins.

**Closing line:**
> “The goal is not to replace a benchmark score with another headline number. It is to make every score inspectable enough that a self-hosting user can see what was tested, what fit on their machine, and what kind of failure was actually observed.”

## 7. Dashboard: how to demo it safely

The Streamlit dashboard is useful for exploration. In the implementation, the selected default “Overall accuracy” is `primary_acc`; data preparation chooses exact match if present, otherwise legacy lexical, otherwise judge. It pools the loaded records and its KPI widgets compute a best-model label, an unweighted-by-run record average, model count, and record count. It does not enforce a matched experimental design in those charts.

### Demo route (no model/GPU inference required)

1. Open the already-generated dashboard/static report from existing archived JSONL results. State that this is a read-only view of saved experiment outputs; you are not starting new inference during the presentation.
2. Start at the model/task comparison only to orient the audience. Immediately say the pooled ranking is descriptive and confounded by unequal contexts, tasks, sample sizes, and historical measurement changes.
3. Select one experiment and one model, then use the context/depth or task-structure view as an exploration. Point out sample sizes when available and avoid extrapolating beyond observed cells.
4. Use the multi-hop view to explain registry size and the two failure modes. Say whether the view is raw accuracy or a different evaluator explicitly.
5. Open data coverage/methodology. Point to 33 runs, 870 records, fingerprint availability, and the self-judged count. Explain that an absent metric is not a zero.
6. Keep a screenshot or the static HTML report as a fallback. Do not trigger a new run or imply that live Ollama/GPU inference is taking place.

### Dashboard limitations to volunteer if asked

- “Average accuracy” is a pooled record average, not a run-balanced estimate or confidence interval.
- Task families are not comparable and differ in case construction/question wording.
- Legacy and current metric names/definitions coexist in archived records.
- Some records have no content fingerprint; old inputs cannot be reconstructed from an output-only archive.
- 443 of the 870 records are marked self-judged, so judge-based scores in those records are not independent evidence.
- Model, context, task, sample size, and run often co-vary. A dashboard line does not establish causality.
- The dashboard currently uses a primary-score fallback across metric versions; this makes it good for browsing but insufficient as the final scientific analysis.

## 8. Likely panel questions and strong answers

Use the short answer first. Stop there if the panel is satisfied; give the technical detail only when asked. If you do not know, state what evidence would answer it rather than guessing.

### Product and motivation

**1. “What does this do that a normal benchmark does not?”**  
**Short answer:** It preserves case-level evidence and serving context so we can diagnose a failure, not only aggregate scores.  
**Detail:** The probe inventory lets us compare the answer to the planted target and decoy values. The record also includes context/provenance/status information. The project’s long-term goal is failure classification and cross-model comparison, but those layers are not yet validated.

**2. “Who is the user?”**  
**Short answer:** Researchers and self-hosters who need to know what a model did under a particular local serving setup.  
**Detail:** For a self-hoster, an advertised context size may exceed available RAM/VRAM. A diagnostic run should disclose the model, context, KV settings, host snapshot where available, and actual response rather than publishing a context-free score.

**3. “Why not just use RULER, BABILong, or a standard NIAH test?”**  
**Short answer:** Those are valuable benchmarks; ProbeBench is focused on an inspectable local evaluation workflow and distinct failure probes.  
**Detail:** It should be compared against established benchmarks, not described as replacing them. Its distinctive engineering emphasis is the preflight plus per-case provenance, while the research ambition is to separate retrieval, discrimination, and composition. A rigorous comparative validation against those suites is still future work.

**4. “Is this a benchmark or a framework?”**  
**Short answer:** Today it is a framework containing three related synthetic experiments and an Ollama runner.  
**Detail:** The common pipeline, registry, result schema/migrations, preflight, evaluators, and dashboard are reusable; the currently implemented benchmark family is long-range dependency. It is not yet a general multi-family benchmark platform in the empirical sense.

### Method and measurement

**5. “What exactly is a successful case?”**  
**Short answer:** In the retrieval-oriented experiments, the answer must assert the expected code; mere mention while denying it is not credited.  
**Detail:** The lexical evaluator checks expected-string containment combined with a narrow repudiation guard. This is deterministic and inexpensive, but it is English-pattern-dependent and the guard’s held-out precision/recall are not established. For keyed experiments the code itself flags the guard as known-optimistic, so those retrieval values must be described as upper bounds until the guard is extended and validated.

**6. “Why is a wrong planted code a different failure from no code?”**  
**Short answer:** One suggests choosing the wrong referent among known candidates; the other suggests failing to produce a candidate at all.  
**Detail:** In the multi-hop inventory, every planted value is mapped to a registry subject. Comparing the returned code to that inventory gives an observable distinction. It does not by itself prove the internal cognitive cause; it labels the response behavior, not the model’s hidden reasoning process.

**7. “How do you know the task itself is valid or solvable?”**  
**Short answer:** The generator knows the target and the keyed inventory by construction, but a completed human-solvability audit is not documented in the current evidence.  
**Detail:** The next protocol should independently verify every generated case and have humans review wording/ambiguity, especially before calling a failure a model capability limitation. A generated answer key is not the same thing as a human-validity study.

**8. “Does needle depth mean dependency distance?”**  
**Short answer:** It is a controlled placement coordinate in a generated long context, not a universal measure of semantic dependency distance.  
**Detail:** The basic NIAH design inserts the target at a normalized depth and asks after the context. Multi-hop changes the structure by making a pointer refer to a separate registry entry. The PDF’s five-bin dependency-distance formulation is a planned presentation protocol, not what every current archived run implements.

**9. “Why do the arms have different prompts?”**  
**Short answer:** Because they test different capabilities; the prompt is part of each task definition.  
**Detail:** This is exactly why their raw accuracies should not be pooled as though task type were a nuisance variable. For a direct comparison, use a pre-registered matched design that holds every other relevant feature fixed or clearly states the estimand.

**10. “How do you control filler effects?”**  
**Short answer:** We record the corpus and inventory, but the current filler is not neutral.  
**Detail:** The NIAH corpus includes *War and Peace*; its opening passage itself contains plausible “secret” content, which has drawn wrong responses. The project identified this as a real confound, not something to hide. A better next design uses more than one controlled filler/corpus or explicitly treats corpus as a factor and reports its effect.

**11. “Is the needle insertion marker artificial?”**  
**Short answer:** Yes; this is a synthetic probe, and marker format can affect behavior.  
**Detail:** The marker/system instruction is part of the measured prompt, not invisible scaffolding. Prior responses sometimes rejected the marked fact as an artifact, especially near the question boundary. That shows why marker choice and boundary conditions need their own controls; a synthetic result does not automatically generalize to ordinary documents.

**12. “Why not score with an LLM judge only?”**  
**Short answer:** A model judge can be useful, but it can fail, share biases, and is not independent ground truth.  
**Detail:** This codebase has archived cases where a judge misgraded correct answers and where a percentage-style prompt yielded an out-of-range score. A repaired prompt fixed a specific defect, but self-judging remains a validity threat. A deterministic rule is preferable where the known inventory makes the answer decidable; human labels are needed to validate ambiguous semantic categories.

**13. “Why is an absent metric better than zero?”**  
**Short answer:** Evaluator failure means “not measured,” not “the model got zero.”  
**Detail:** If an unavailable judge result is set to zero, the aggregate is biased downward and confounds inference failure with evaluation failure. The result records errors/status separately and leaves the metric absent. Aggregation must report a denominator per metric.

**14. “How do you ensure fair model comparisons?”**  
**Short answer:** The current archive is not sufficiently matched to support a clean universal ranking.  
**Detail:** A fair comparison should use the same content-addressed cases, same task wording, same context/position cells, and documented inference options, with repeated trials where generation is stochastic. Different tokenizers complicate “same token length”: even with identical text, the model-native prompt token counts can differ. The current project records enough identity for newer records to support some joins, but legacy rows and unequal runs prevent a complete comparison today.

### Systems and local inference

**15. “Why does context consume so much memory?”**  
**Short answer:** The transformer keeps key/value state for each token across layers; the cache grows roughly linearly with sequence length.  
**Detail:** For the formula in section 3, the factor 2 is K and V. GQA lowers the number of KV heads relative to query heads, but the exact result depends on the model geometry and cache element size. The estimate covers KV cache; total runtime memory also includes weights and other buffers.

**16. “Is the memory prediction exact?”**  
**Short answer:** The KV-cache arithmetic is geometry-based and was checked against a real allocation; the total-memory feasibility verdict is an estimate with a safety budget.  
**Detail:** It does not perfectly model compute buffers, allocator fragmentation, driver/runtime allocations, dynamic contention, or every device/backend. It samples available memory and combines a weight estimate, KV estimate, and buffer margin. That makes it a useful preflight, not a promise that inference must succeed.

**17. “What if Ollama is on another machine?”**  
**Short answer:** The framework can target a remote Ollama endpoint, but client-side hardware information is not server hardware information.  
**Detail:** The project deliberately records host hardware as unknown/null when the Ollama server is remote rather than silently attributing the client’s GPU/RAM to the inference host. Server-side telemetry/probing is a remaining gap. Always distinguish client and server when reporting remote runs.

**18. “Does it require a GPU?”**  
**Short answer:** It does not require a GPU to present the saved results or to explain the code; inference performance and feasible model/context depend on the host.  
**Detail:** The project’s goal is self-hosted inference through Ollama, and memory feasibility includes RAM/VRAM. CPU inference may be possible but can be slow and is not the performance configuration represented by every archived result. For this presentation, use the saved JSONL/dashboard and do not launch inference.

**19. “Why use two-phase execution?”**  
**Short answer:** Generate all answers first, then evaluate them, to reduce repeated model unload/reload pressure in Ollama.  
**Detail:** Ollama runner identity depends on model/context options. Interleaving a generation model and judge can evict/reload runners. Two-phase execution reduces churn and makes judging more stable/efficient on memory-constrained local hardware. It has a tradeoff: without checkpoints, a crash before evaluation/output completion can lose work; single-phase mode exists as a safer incremental-write option.

**20. “Which backend and models are supported?”**  
**Short answer:** The current implemented inference backend is Ollama; current archived tags are the four listed in section 5.  
**Detail:** Do not imply that the current experiment used llama.cpp or that model families in the PDF have completed runs. Backend abstraction and other model-serving setups are future scope, not evidence in these results.

### Results, stats, and claims

**21. “Is qwen3:4b the best model?”**  
**Short answer:** Not established. It scored 100% on its cases in this archive, but it was not tested on the same balanced set as every other model.  
**Detail:** `qwen3:4b` has different task/context coverage and fewer NIAH cases than `llama3:8b`; `llama3.2:1b` only has six NIAH records around 128K. Selection effects, task mix, and sample size make “best model” a dashboard convenience, not a fair leaderboard conclusion.

**22. “Why does the dashboard say 88%?”**  
**Short answer:** It is the mean of the default `primary_acc` over the loaded 870 records, and `primary_acc` uses a fallback across metric keys. It is not a curated benchmark result.  
**Detail:** The loader maps exact-match, legacy lexical, or judge depending on the field available, and the dashboard pools distinct experiments/runs with unequal counts. It also includes self-judged rows, historical metric revisions, and 400 records without fingerprints. Use the number only to explain the exploratory UI; do not quote it as a validated overall accuracy.

**23. “What does the 16/50 result establish?”**  
**Short answer:** It establishes that this specific qwen3:0.6b multi-hop run produced a nontrivial set of observable failures at roughly 4K; it motivates replication.  
**Detail:** It does not establish a general context threshold or model-family effect. The observed 9 no-code and 7 wrong-planted-code categories are behavioral descriptions from a finite corpus. We need more models, independent runs, controlled registry rotations/subjects, and human review before broader claims.

**24. “Why are there no confidence intervals or significance tests?”**  
**Short answer:** Many cells have too few independent repetitions; a single case per cell cannot estimate variability.  
**Detail:** The default grid has historically used one needle per configuration, and the archive aggregates runs with different designs. The responsible next step is repeated trials, a pinned sampling configuration/seed where supported, and a pre-registered unit of analysis. Reporting a confidence interval without a defensible sampling model would create false precision.

**25. “Are the runs reproducible?”**  
**Short answer:** Not fully. The records preserve useful provenance and case identity, but seed control and some prompt/version metadata are incomplete.  
**Detail:** Generation can inherit serving/model defaults, and the project has no general seed option. Tokenizer mismatch means nominal context counts do not guarantee equal model-native token counts. Newer records include content fingerprints, but 400 archive records lack them. Reproduction should pin explicit settings and compare fingerprints rather than relying on case IDs alone.

**26. “Can you claim the model architecture caused the difference?”**  
**Short answer:** No. These are behavioral observations across model tags, not a causal architecture experiment.  
**Detail:** Models differ in training data, tokenizer, instruction tuning, quantization, and serving implementation, in addition to architecture. To isolate architecture causally would require much tighter controls than the current archive offers. Use “observed model behavior” and not “architecture caused.”

**27. “Why do you have a taxonomy if it is not implemented?”**  
**Short answer:** The taxonomy is a design target informed by observed responses; it is not yet a validated product feature.  
**Detail:** The correct order is to collect a failure corpus, hand-label a sample, check whether proposed categories are reachable and mutually distinguishable, then measure rule/LLM performance against ground truth. A label list alone is a hypothesis. We have an initial 16/50 multi-hop failure set, but the planned human-labelled n≈100 evaluation and per-label precision/recall are not complete.

**28. “What is your next experiment?”**  
**Short answer:** Replicate and deconfound the multi-hop signal, then human-label failures before claiming a taxonomy.  
**Detail:** A useful sequence is (1) rotate registry layout so rank and subject identity are separated; (2) run more than one model with matched cases/settings; (3) repeat cells; (4) record exact model-native prompt token counts and all run settings; (5) obtain blind human labels on a sample and ideally a second annotator; (6) report rule/LLM disagreement, per-label precision/recall, and failure-set overlap only over fingerprint-matched cases.

### Project quality and contribution

**29. “What is your main technical contribution?”**  
**Short answer:** The combination of memory-aware local evaluation and inspectable per-case failure evidence, with task designs that separate retrieval from discrimination and composition.  
**Detail:** The memory preflight is grounded in a real allocation incident and validated against the observed KV-cache request. The multi-hop case inventory makes wrong planted retrieval inspectable. The broader classifier/cross-model claims are planned, so phrase the contribution as a working foundation and early empirical demonstration.

**30. “What is novel compared with just writing a script?”**  
**Short answer:** It turns one-off local model calls into a controlled, provenance-carrying experiment with feasibility planning, failure isolation, versioned records, and reusable registered experiments.  
**Detail:** Novelty should not rest on saying no one has ever run NIAH. The defensible value is the integration and the research process: avoid infeasible contexts before loading, retain case-level results, separate task types, and inspect constructed failure modes. A literature/prior-art comparison still needs to be made carefully before claiming scientific novelty.

**31. “What is the weakest part of the current evidence?”**  
**Short answer:** The current cross-model and pooled dashboard summaries are not matched, repeated, or independently validated enough for broad claims.  
**Detail:** Specific gaps include cl100k-vs-model tokenizer mismatch, no seed control, few repeats, self-judged rows, historical metric changes, legacy rows without fingerprints, lexical guard limitations, and no hand-labelled taxonomy validation. Naming these is part of the result, not a reason to hide the prototype.

**32. “What will you do if a result contradicts your expectation?”**  
**Short answer:** Preserve the raw output and configuration first, isolate one variable at a time, and revise the claim rather than explain away the result.  
**Detail:** The repository keeps a research journal and decision record for exactly this reason. A failure can be an evaluator artifact, serving artifact, or benchmark-design issue; the next experiment should distinguish these before attributing it to the model.

## 9. Hostile-question handling: a four-step response

For a difficult technical challenge:

1. **Answer the literal question in one sentence.** Avoid a long preamble.
2. **Name the evidence.** “The archived multi-hop run is 50 cases on qwen3:0.6b.”
3. **State the boundary.** “It is not replicated and does not generalize by itself.”
4. **Offer the discriminating next test.** “We would rotate registry order and hold subject identity fixed.”

Useful phrases:

- “That is a planned capability, not a result we have measured yet.”
- “The data support an observation, not that causal conclusion.”
- “I don’t have that number in the archive; I would not want to guess.”
- “That metric is exploratory here because its denominator/design is not controlled.”
- “The failure response is observable; the model’s hidden internal cause is not.”

Avoid answering a question about reproducibility with a generic statement that JSONL is deterministic. Storage is not the same as repeatable inference. Avoid defending an old slide sentence just because it is printed; correct the statement and move to the evidence.

## 10. Final pre-presentation checklist

### Correct the claims in the slides

- [ ] Mark the Llama-2/Mistral comparison as **proposed**, or replace it with the actual current model tags.
- [ ] Mark fixed-seed, temperature-0, llama.cpp/Q4_K_M inference as **planned**, not completed.
- [ ] Replace “~500 probes” with the precise description “870 archived case records across 33 runs,” if using the current results snapshot; do not imply all are unique/independent.
- [ ] Mark human solvability checks, hand-labelled failure taxonomy, Cohen’s κ, and Jaccard results as future evaluation unless new evidence is produced.
- [ ] State that there are three non-comparable task arms: NIAH, distractor, multi-hop.
- [ ] State the multi-hop result with model, n, context, and failure breakdown.
- [ ] Do not present the dashboard’s 88% average or best-model card as the headline scientific conclusion.

### Prepare the technical backup

- [ ] Have the KV-cache formula and qwen3:4b arithmetic ready.
- [ ] Know the archive coverage: 870 rows, 33 runs, four model tags, three experiments; 470 fingerprints, 400 without; 443 self-judged.
- [ ] Be ready to distinguish actual behavior labels from hidden reasoning claims.
- [ ] Have a static report/screenshot and a sample JSONL row available; no new inference is needed.
- [ ] Mention tokenizer mismatch and lack of repeats/seed before a judge has to uncover them.
- [ ] Make one team member responsible for implementation, another for experimental design/results, and another for limitations/next steps; all speakers should agree on the scope contract above.

## 11. Source trail

The principal checked sources for this guide are:

- Attached competition deck: [Avishkar 2026-Probebench.pdf](../Avishkar%202026-Probebench.pdf)
- Project overview and CLI: [README.md](../README.md)
- Current status, invariants, and planned architecture: [CLAUDE.md](../CLAUDE.md)
- Architecture and measured KV-cache derivation: [DESIGN.md](DESIGN.md)
- Measurement threats: [LIMITATIONS.md](LIMITATIONS.md)
- Decision history: [DECISIONS.md](DECISIONS.md)
- Observed result chronology: [JOURNAL.md](JOURNAL.md)
- Verified fixes/residuals: [RESOLVED.md](RESOLVED.md)
- Dataset/experiment source map: [CODEMAP.md](CODEMAP.md)
- Shared dashboard data prep, chart definitions, findings, and KPIs: [dashboard_core.py](../dashboard_core.py)
- Streamlit UI and filters: [dashboard.py](../dashboard.py)
- Static HTML report generator: [generate_dashboard_html.py](../generate_dashboard_html.py)
- Registry of the three current experiments: [registry.py](../src/probebench/experiments/registry.py)
- NIAH case construction: [benchmark.py](../src/probebench/benchmarks/long_range_dependency/NIAH/benchmark.py)
- Multi-hop case construction and inventory: [benchmark.py](../src/probebench/benchmarks/long_range_dependency/NIAH_multihop/benchmark.py)
- Deterministic lexical evaluator and repudiation guard: [lexical.py](../src/probebench/evaluation/long_range_dependency/NIAH/lexical.py)
- Current stored experiment output: [results](../results)

**Scope note:** the archive figures in this document describe the JSONL files available in the workspace on 2026-09-30 and the current dashboard loader’s interpretation. If results are added or files change, refresh all counts and aggregates before presenting them.
