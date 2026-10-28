# ProbeBench React Studio (v2.0)

A high-performance, modern diagnostic frontend for **ProbeBench** LLM evaluations, fully converted from Streamlit to React.

## 🚀 Key Improvements Over Streamlit

1. **Zero-Rerun Architecture**: Fast client-side filtering and chart updates without full Python script restarts.
2. **Dedicated Modular Pages**: Distinct pages for every diagnostic perspective instead of a crowded single-page layout.
3. **Model Comparison Lab**: Head-to-head model comparison with distinct color palettes (Electric Cyan vs. Neon Rose), differential delta matrices ($Model_A - Model_B$), and overlaid context scaling curves.
4. **Interactive Case Inspector**: Inspection of every single failure with side-by-side ground truth vs. actual generation, repudiation classification, and copy tools.
5. **Preloaded Real Benchmarks**: Preloaded with actual 4K–32K and 2K–8K benchmark archives from `probebench/results/reports`, plus instant drag-and-drop support for any custom CSV or JSON run.

---

## 📑 Diagnostic Pages Overview

| Page | Route | Description |
| :--- | :--- | :--- |
| **Executive Overview** | `/dashboard` | High-level KPIs, 4-tier taxonomy progress bars, repudiation warnings, and key diagnostic takeaways. |
| **2D NIAH Heatmap** | `/heatmaps` | Flagship Context Length ($X$) × Needle Depth ($Y$) matrix with interactive cell inspector and metric toggle (Semantic, Lexical, Harness Reported, Denial Rate). |
| **Retrieval Curves** | `/trends` | Degradation curves for Accuracy vs. Context Length and Accuracy vs. Depth positional biases. |
| **Failure Inspector** | `/failures` | Stacked failure breakdown across context windows + case-by-case inspection of ground-truth needle vs. model prediction. |
| **Model Compare Lab** | `/comparison` | Head-to-head comparison using distinct calibrated color systems (Electric Cyan vs. Neon Rose), cell-by-cell advantage matrix, and latency deltas. |
| **Latency & Compute** | `/latency` | Scatter plot of inference latency vs. tokens, plus bucketed mean latency with $\pm 1\sigma$ error bars. |
| **Raw Data Explorer** | `/data` | Searchable, paginated data grid with live export to CSV and JSON. |
| **AI Judge Studio** | `/judge` | Interactive classifier testing playground for auditing ambiguous responses against deterministic rule guardrails. |

---

## 🛠️ Quick Start

```bash
# From the repo root:
./scripts/start_frontend.sh

# Or directly from the frontend directory:
cd probebench/frontend
npm run dev
```

Open your browser at `http://localhost:3000`.

