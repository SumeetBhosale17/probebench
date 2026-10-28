# Probebench results snapshot: key findings and conclusions

**Scope:** the supplied `results.zip` snapshot, inspected on 22 October 2026. Findings are based on the 38 JSONL run files and 1,230 parsed records. These are observed results, not claims about model capability beyond the tested tasks and settings.

## Dataset inventory and integrity

- **1,230 records** across **38 JSONL files/runs** and four task designs:
  - NIAH: 604 records
  - Negative retrieval: 360 records
  - NIAH multihop: 176 records
  - NIAH with distractors: 90 records
- Schema distribution: 1.0: 380; 1.1: 20; 1.2: 4; 1.3: 20; 1.4: 166; 1.5: 68; 1.6: 572.
- There were **no malformed JSONL lines** in the supplied files. The archive has 34 records with missing/unknown response status and one `evaluation_error` status.
- Model labels resolve to four variants after handling early-schema `model` values saved as strings: Qwen3 0.6B (610 records), Llama 3 8B (385), Qwen3 4B (229), and Llama 3.2 1B (6).
- 830 records have `case_key` values, representing 556 distinct keys. This means many records repeat case designs across runs/prompts; 1,230 is a record count, not a count of independent unique cases.
- Across all records, median latency is 7.50 s, mean latency is 18.03 s, and p95 latency is 80.00 s. The p95 is about 10.7 times the median. This mixes tasks and context lengths and should not be used to rank model speed.
- In the 830 records with both `prompt_eval_count` and `num_ctx`, no prompt token count exceeded the logged context setting.

## Finding 1 — A strict extractor prompt improves abstention more than retrieval

Three Qwen3 0.6B runs share the same 40 case keys at roughly 4K context. The baseline prompt scored 0% answerability exact match (0/20 answerable, 0/20 unanswerable). The stricter extractor prompt scored 57.5% overall: 3/20 answerable cases were retrieved exactly (15%), while all 20/20 unanswerable cases were correctly answered with the required abstention string (100%).

**Conclusion:** the prompt change substantially improves correct abstention on these shared cases, but answerable retrieval remains weak at 15%. The main next step is improving retrieval of present facts without regressing refusal behaviour on absent facts.

A third run evaluated with Qwen3 4B as judge scored 55% overall (15% answerable retrieval, 95% correct abstention). The strict-prompt runs have different judge-model configurations and saved predictions differ on 8 of 40 shared cases. The small score difference should not be attributed to the judge model alone; generation variability/configuration is a confound.

A separate 160-record baseline-prompt run spanning approximately 4K, 8K, 16K and 32K contexts scored 0% answerability exact match at every context size. Its p95 latency was 111.33 s, with the largest latency increase appearing in the 32K cases. Increasing context length alone did not fix the observed prompt/answerability failure in that run.

## Finding 2 — Qwen3 0.6B NIAH accuracy degrades mildly by context size, while format compliance degrades sharply

In run `478efbee30ab` (90 NIAH cases), context buckets have 30 cases each:

| Context | Lexical exact match | LLM judge | Instruction compliance | Median latency |
|---|---:|---:|---:|---:|
| ~8K | 100.0% | 100.0% | 100.0% | 5.28 s |
| ~16K | 96.7% | ~100.0% | 96.7% | 8.56 s |
| ~32K | 93.3% | 93.2% | 16.7% | 19.01 s |

**Conclusion:** answer presence remains high in this run through 32K, but median latency increases about 3.6× from 8K to 32K, and strict-format compliance collapses at 32K. Answer correctness and response-format adherence must be measured separately.

## Finding 3 — Llama 3 8B NIAH is strongly sensitive to needle position in one 330-case run

In run `2bfcd3f32b11`, with 30 cases at each depth, lexical exact match is 6.7% at depth 0%, rises to 96.7% at 40–50% depth, and falls to 63.3% at depth 100%.

**Conclusion:** the tested run shows a strong position effect: the opening edge is especially weak, the middle is stronger, and the final edge is also weaker than the middle. This finding is limited to this run's model, context lengths (~7K–8K), prompt and schema 1.0 results.

## Finding 4 — Qwen3 4B produces high saved scores on distractor and multihop tests, but costs more latency

- NIAH distractor run `aadb46540671`: 60 cases; 100% lexical exact match, LLM judge and instruction compliance. Median latency is about 13.70 s at ~4K and 37.46 s at ~8K—roughly 2.7× higher at the longer context bucket.
- NIAH multihop run `63b9fdb9f911`: 120 cases; 100% lexical exact match and LLM judge, 98.3% instruction compliance. Median latency is 23.75 s around 4K and 61.61 s around 8K.
- The Qwen3 0.6B multihop run `54630557c081` has 50 cases, 68.0% lexical exact match and 78.0% instruction compliance, with 2.43 s median latency. Only six `case_key` values overlap with the Qwen3 4B multihop run.

**Conclusion:** the saved Qwen3 4B results are strong on these specific samples but have substantial latency costs. Since the 0.6B and 4B multihop runs overlap on only six case keys, they are not a controlled head-to-head model comparison.

## Finding 5 — Metric labels need an explicit semantic check

In the saved NIAH outputs, `lexical_exact_match` sometimes equals 1.0 even when the prediction includes the expected code inside additional explanatory prose, while `instruction_compliance` is 0.0. For example, a response can contain `8829-BETA-Z` in a sentence and still receive lexical exact match = 1.0 and instruction compliance = 0.0.

**Conclusion:** in these results, `lexical_exact_match` should not be interpreted as strict whole-response string equality or format compliance. Audit the metric implementation and document whether it means substring/normalized answer presence, then keep it separate from an exact-output metric. In addition, 24 early-schema records use a metric named `lexical` rather than `lexical_exact_match`; do not merge the two without verifying definitions.

## Recommended next steps

1. Preserve the result archive as the source of truth and keep metrics task-specific.
2. For prompt experiments, reuse the same `case_key` set, model, generation parameters and random seed where possible; log judge model/config separately from generator config.
3. Report answerable retrieval, correct abstention and format compliance as separate metrics for negative retrieval.
4. Audit exact-match semantics and use distinct names for strict whole-string equality versus answer presence.
5. Make context/depth charts run-selectable and bucket near-identical token counts, rather than plotting every run on one axis.
6. When comparing models, compare the same case keys and settings; if overlap is small, label the result exploratory.
