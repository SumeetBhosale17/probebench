# NIAH Evaluation Dashboard

A Streamlit dashboard for analyzing Needle-in-a-Haystack (long-range dependency) results, scoring each response on **lexical exact-match** and **semantic/logical correctness** separately, with interactive heatmaps and trend charts.

## Setup

```bash
cd /home/siddhant/Travelling/Capstone/probebench
python3 -m venv .venv
source .venv/bin/activate
pip install -r Sem-Analyzer/requirements.txt
```

Create the root `.env` file if it does not already exist:

```bash
cp .env.example .env
```

Set `RESULT_FILE_PATH` in the root `.env` to the CSV you want the dashboard to load:

```env
RESULT_FILE_PATH=results/benchmarking_raw.csv
```

Relative paths are resolved from the repo root. Absolute paths and `~` paths are also supported.

## Run

From the repo root:

```bash
source .venv/bin/activate
streamlit run Sem-Analyzer/niah_dashboard.py
```

Or from inside `Sem-Analyzer`:

```bash
source ../.venv/bin/activate
streamlit run niah_dashboard.py
```

The app opens in your browser, usually at `http://localhost:8501`.

By default, the dashboard loads the CSV configured in `RESULT_FILE_PATH`. You can still use the **Upload results CSV** control in the sidebar to override the env-configured file for the current session.

Expected CSV columns:

- `context_tokens`
- `depth`
- `needle`
- `predicted`
- `success` (optional; recomputed if missing)
- `latency_sec` (optional)
- `context_tokens_binned` (optional; recomputed if missing)

## What it does

- **Recomputes lexical match** independently of your harness's `success` column, and adds a 4-tier correctness taxonomy per row: Exact/Clean Match, Correct (Verbose), Correct but Denied/Confused, Hallucinated/Wrong.
- **Semantic/logical correctness** excludes the "Denied/Confused" case — responses where the model found the right text but talked itself out of it — since those aren't reliable answers even though the substring is technically present.
- **Heatmaps & trends tab**: the classic context-length × depth NIAH heatmap (toggle between lexical / semantic / harness-reported metrics), plus accuracy-vs-context and accuracy-vs-depth charts.
- **Failure analysis tab**: category breakdown, stacked bar by context length, and a row-by-row inspector for reading full predictions against the ground-truth needle.
- **Latency tab**: latency vs. context length scatter, plus mean/std by context bucket.
- **Raw data & export tab**: searchable table of all annotated rows + CSV download.
- **AI Judge tab (optional)**: send ambiguous rows to Claude for a second opinion, using your own Anthropic API key. Entirely optional — the rest of the dashboard works fully offline.
