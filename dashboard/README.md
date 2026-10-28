# Probebench Evaluation Lab

A local, interactive dashboard for saved Probebench JSONL results. It scans nested `*.jsonl` files recursively, normalizes fields observed across schema versions 1.0–1.6, and leaves unavailable values missing rather than silently converting them to zero.

## Run locally

Run from the Probebench repository root:

```bash
python -m venv .venv-dashboard
source .venv-dashboard/bin/activate
python -m pip install -r dashboard/requirements.txt
PROBEBENCH_RESULTS_DIR=results python -m streamlit run dashboard/app.py
```

Windows PowerShell:

```powershell
python -m venv .venv-dashboard
.venv-dashboard\Scripts\Activate.ps1
python -m pip install -r dashboard/requirements.txt
$env:PROBEBENCH_RESULTS_DIR = "results"
python -m streamlit run dashboard/app.py
```

The results folder can contain nested directories. `.log` and report files are not parsed as case records. After generating new output, click **Refresh results**. The dashboard does not run benchmarks or modify result files.

## Views

- **Overview:** brief evidence-based readout plus metric summaries grouped by task × model × schema rather than 38 per-run labels.
- **Findings & conclusions:** archive inventory, case studies, observed results, interpretation limits, and recommended follow-up experiments. It includes a downloadable Markdown audit when the supplied archive's reference runs are present.
- **Capability & context:** choose one run at a time to plot score versus context length and retrieval depth, plus a context × depth heatmap. This prevents 38 overlapping lines and long legends.
- **Inference cost:** select a task to inspect latency distributions and context/latency effects. Legend categories are models, not run IDs.
- **Case explorer:** inspect expected/predicted text, status, metrics and original JSON records.
- **Data quality:** schema coverage, unknown statuses, response/evaluation errors, missing fields, context configuration and parse diagnostics.

## Interpretation guardrails

- Do not calculate one global score across unrelated tasks or metric names.
- Model results may not be directly comparable unless case set, prompts, generation parameters, hardware and evaluator settings align.
- The supplied archive contains `lexical_exact_match = 1.0` cases where the correct answer appears inside additional prose while instruction compliance is zero. Audit the metric implementation before treating it as strict whole-response equality.
- The saved run-specific report refers to the supplied archive snapshot. Use it as evidence about these experiments, not as a claim about all model behaviour.

## Streamlit / Starlette gzip compatibility

If `GZipResponder.__init__()` raises a `thread_minimum_size` error, use this dashboard-specific virtual environment and requirements file. Avoid changing the benchmark runner's primary environment unless you understand the impact on that environment.
