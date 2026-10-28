from __future__ import annotations

import os
import statistics
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_loader import discover_jsonl_files, file_fingerprint, read_jsonl_files

st.set_page_config(
    page_title="Probebench · Evaluation Lab",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      html, body, [class*="css"] { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      .stApp { background: #0b0f14; color: #e7edf4; }
      [data-testid="stHeader"] { background: rgba(11,15,20,.92); }
      [data-testid="stSidebar"] { background: #10161e; border-right: 1px solid #202a35; }
      [data-testid="stMetric"] { background: linear-gradient(145deg,#121a23,#0f151d); border: 1px solid #263341; padding: 15px 17px; border-radius: 14px; }
      [data-testid="stMetricLabel"] { color: #9bacbd; font-size: .82rem; }
      [data-testid="stMetricValue"] { color: #f2f7fb; font-weight: 800; }
      .eyebrow { color: #55dbc6; font-family: 'DM Mono', monospace; letter-spacing: .14em; font-size: .72rem; text-transform: uppercase; }
      .hero-title { font-size: clamp(2rem, 4vw, 3rem); font-weight: 800; letter-spacing: -.055em; line-height: 1.05; color: #f5f8fb; margin: .3rem 0 .65rem 0; }
      .hero-copy { color: #9bacbd; max-width: 900px; line-height: 1.65; font-size: .98rem; }
      .small-muted { color: #91a2b4; font-size: .82rem; }
      h1, h2, h3 { letter-spacing: -.035em; }
      div[data-testid="stDataFrame"] { border: 1px solid #263341; border-radius: 12px; overflow: hidden; }
      code, pre { font-family: 'DM Mono', monospace !important; }
      .stAlert { border-radius: 12px; }
      div[data-testid="stTabs"] button { font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

PERCENT_METRIC_FRAGMENTS = ("exact_match", "instruction_compliance", "llm_judge")
KNOWN_SCHEMA_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6"}


def metric_label(column: str) -> str:
    return column.removeprefix("metric__").replace("_", " ").title()


def is_percent_metric(column: str) -> bool:
    name = column.removeprefix("metric__").lower()
    return any(fragment in name for fragment in PERCENT_METRIC_FRAGMENTS)


def nice_metric(value: float, metric_col: str) -> str:
    if pd.isna(value):
        return "—"
    if is_percent_metric(metric_col):
        return f"{value * 100:.1f}%"
    return f"{value:.3f}"


def percentile(series: pd.Series, p: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.quantile(p))


def plot_layout(fig, height: int = 360, legend: bool = True):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#cad5e1", size=12),
        margin=dict(l=16, r=18, t=54, b=44),
        hoverlabel=dict(bgcolor="#17212c", font_color="#f5f8fb"),
    )
    if legend:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    else:
        fig.update_layout(showlegend=False)
    fig.update_xaxes(gridcolor="#263341", zerolinecolor="#263341", linecolor="#263341")
    fig.update_yaxes(gridcolor="#263341", zerolinecolor="#263341", linecolor="#263341")
    return fig


def short_task(benchmark: str, experiment: str) -> str:
    task_map = {
        ("long_range_dependency", "NIAH"): "NIAH",
        ("long_range_dependency", "NIAH_distractor"): "NIAH · distractors",
        ("long_range_dependency", "NIAH_multihop"): "NIAH · multihop",
        ("long_context_understanding", "negative_retrieval"): "Negative retrieval",
    }
    return task_map.get((str(benchmark), str(experiment)), f"{benchmark} · {experiment}")


def add_task_labels(data: pd.DataFrame, results_root: str) -> pd.DataFrame:
    data = data.copy()
    data["task_label"] = data.apply(lambda r: f"{r['benchmark']} / {r['experiment']}", axis=1)
    data["task_short"] = data.apply(lambda r: short_task(r["benchmark"], r["experiment"]), axis=1)
    data["context_length"] = pd.to_numeric(data["context_tokens"], errors="coerce").where(
        pd.to_numeric(data["context_tokens"], errors="coerce").notna(),
        pd.to_numeric(data["target_tokens"], errors="coerce"),
    )

    root_path = Path(results_root).expanduser()
    try:
        root_path = root_path.resolve()
    except OSError:
        pass
    root_is_dir = root_path.is_dir()

    def source_label(path_string: str) -> str:
        path = Path(str(path_string))
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if root_is_dir:
            try:
                return resolved.relative_to(root_path).as_posix()
            except ValueError:
                pass
        return path.name

    data["source_label"] = data["source_file"].map(source_label)
    data["run_key"] = data["source_file"].astype(str) + "::" + data["run_id"].astype(str)
    return data


def run_catalog(data: pd.DataFrame, metric_col: str | None = None) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["run_key", "run_label", "cases"])
    grouped = data.groupby(
        ["run_key", "source_file", "source_label", "run_id", "benchmark", "experiment", "model_name", "schema_version"],
        dropna=False,
    )
    if metric_col and metric_col in data:
        summary = grouped.agg(cases=(metric_col, "count"), total_cases=("case_id", "count")).reset_index()
    else:
        summary = grouped.agg(cases=("case_id", "count"), total_cases=("case_id", "count")).reset_index()
    summary["run_label"] = summary.apply(
        lambda r: f"{short_task(r['benchmark'], r['experiment'])} · {r['model_name']} · v{r['schema_version']} · {str(r['run_id'])[:6]} · n={int(r['total_cases'])}",
        axis=1,
    )
    return summary.sort_values(["cases", "run_id"], ascending=[False, True]).reset_index(drop=True)


def run_rows(data: pd.DataFrame, run_id: str) -> pd.DataFrame:
    return data[data["run_id"].astype(str).eq(str(run_id))].copy()


def class_score(data: pd.DataFrame, answerable: bool) -> float | None:
    metric = "metric__answerability_exact_match"
    if metric not in data.columns:
        return None
    rows = data[data["answerable"].eq(answerable)]
    vals = pd.to_numeric(rows[metric], errors="coerce").dropna()
    return float(vals.mean()) if not vals.empty else None


with st.sidebar:
    st.markdown('<div class="eyebrow">PROBEBENCH</div>', unsafe_allow_html=True)
    st.markdown("## Evaluation Lab")
    st.caption("Local-first analysis of saved result artifacts")
    results_root = st.text_input(
        "Results folder or JSONL file",
        value=os.environ.get("PROBEBENCH_RESULTS_DIR", "results"),
        help="Paths are resolved from the directory where Streamlit was launched. All nested folders are scanned recursively.",
    )
    if st.button("↻ Refresh results", width="stretch"):
        st.cache_data.clear()
        st.rerun()
files = discover_jsonl_files(results_root)
if not files:
    st.markdown('<div class="eyebrow">NO DATA LOADED</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Your results, made legible.</div>', unsafe_allow_html=True)
    st.markdown(
        "Point the dashboard at the directory containing your `.jsonl` result files. Nested directories are scanned. "
        "JSONL files are the source of truth; `.log` and report files are not treated as result records.",
        unsafe_allow_html=True,
    )
    st.info(f"No JSONL files found at `{results_root}`. Try your actual results directory, for example `results/`.")
    st.stop()

fingerprint = file_fingerprint(files)

@st.cache_data(show_spinner="Reading Probebench results…")
def cached_load(fingerprint_arg):
    return read_jsonl_files(fingerprint_arg)

records, diagnostics = cached_load(fingerprint)
if not records:
    st.error("Files were found, but no valid Probebench result records could be loaded.")
    if diagnostics:
        st.dataframe(pd.DataFrame(diagnostics), width="stretch", hide_index=True)
    st.stop()

all_df = add_task_labels(pd.DataFrame(records), results_root)
metric_columns = sorted(c for c in all_df.columns if c.startswith("metric__") and all_df[c].notna().any())
reference_run_ids = {
    "b0ee1fb9c668", "bd41b94deb6e", "54c6c18eeebc", "478efbee30ab",
    "2bfcd3f32b11", "aadb46540671", "63b9fdb9f911", "54630557c081",
}
available_run_ids = set(all_df["run_id"].astype(str))
has_reference_analysis = all(any(rid in value for value in available_run_ids) for rid in reference_run_ids)

# Filters are tucked into an expander so 38 file names don't permanently occupy the sidebar.
with st.sidebar:
    with st.expander("Filters", expanded=False):
        schema_options = sorted(all_df["schema_version"].dropna().astype(str).unique().tolist())
        selected_schemas = st.multiselect("Schema version", schema_options, default=schema_options)
        benchmark_options = sorted(all_df["benchmark"].dropna().astype(str).unique().tolist())
        selected_benchmarks = st.multiselect("Benchmark", benchmark_options, default=benchmark_options)
        filtered_for_experiments = all_df[all_df["benchmark"].astype(str).isin(selected_benchmarks)]
        experiment_options = sorted(filtered_for_experiments["experiment"].dropna().astype(str).unique().tolist())
        selected_experiments = st.multiselect("Experiment", experiment_options, default=experiment_options)
        filtered_for_models = filtered_for_experiments[filtered_for_experiments["experiment"].astype(str).isin(selected_experiments)]
        model_options = sorted(filtered_for_models["model_name"].dropna().astype(str).unique().tolist())
        selected_models = st.multiselect("Model", model_options, default=model_options)
        source_options = sorted(all_df["source_label"].astype(str).unique().tolist())
        selected_sources = st.multiselect(
            "Specific result files (optional)", source_options, default=[],
            help="Leave empty to include all JSONL files. Paths are relative to the selected results folder.",
        )

mask = (
    all_df["schema_version"].astype(str).isin(selected_schemas)
    & all_df["benchmark"].astype(str).isin(selected_benchmarks)
    & all_df["experiment"].astype(str).isin(selected_experiments)
    & all_df["model_name"].astype(str).isin(selected_models)
)
if selected_sources:
    mask &= all_df["source_label"].astype(str).isin(selected_sources)
df = all_df[mask].copy()
if df.empty:
    st.warning("The current filters match no records. Widen the filters in the sidebar.")
    st.stop()

st.markdown('<div class="eyebrow">LLM EVALUATION · RESULT EXPLORER</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">From raw runs to useful evidence.</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-copy">Inspect capability, failure modes, context sensitivity and inference cost from saved result artifacts. '
    'The dashboard keeps benchmarks and metrics separate so a single global score does not disguise incompatible experiments.</div>',
    unsafe_allow_html=True,
)
st.caption("Research snapshot: Findings & conclusions contains the evidence-based readout for the supplied results. Use the charts for diagnosis, not as a universal leaderboard.")
st.write("")

versions_in_view = sorted(df["schema_version"].dropna().astype(str).unique().tolist())
unrecognised_versions = [v for v in versions_in_view if v not in KNOWN_SCHEMA_VERSIONS]
if unrecognised_versions:
    st.warning(
        "Schema version(s) not recognised by this dashboard: "
        f"{', '.join(unrecognised_versions)}. Shared fields are displayed where available; validate semantics before comparing scores."
    )
if len(versions_in_view) > 1:
    st.info("Mixed schema versions are selected. Missing fields remain missing. Compare metrics only when their definitions and case designs are compatible.")
if df["has_error"].any():
    st.warning(f"{int(df['has_error'].sum()):,} record(s) have an error or evaluation-error status in this selection.")
unknown_status = int(df["response_status"].astype(str).str.lower().eq("unknown").sum())
if unknown_status:
    st.caption(f"Response status is missing/unknown for {unknown_status:,} record(s); these are not counted as confirmed failures.")

runs = df[["source_file", "run_id"]].drop_duplicates().shape[0]
models_count = df["model_name"].nunique()
case_count = len(df)
error_rate = float(df["has_error"].mean()) if len(df) else 0.0
latency_values = pd.to_numeric(df["latency_sec"], errors="coerce").dropna()
p50_latency = percentile(latency_values, 0.5)
p95_latency = percentile(latency_values, 0.95)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Evaluated records", f"{case_count:,}")
c2.metric("JSONL files / runs", f"{runs:,}")
c3.metric("Models represented", f"{models_count:,}")
c4.metric("Error / eval-error rate", f"{error_rate * 100:.1f}%")
c5.metric("Median latency", f"{p50_latency:.2f}s" if p50_latency is not None else "—")

with st.expander("Automatic signals for the current selection", expanded=False):
    observations = []
    task_count = df["task_label"].nunique()
    if p95_latency is not None and p50_latency is not None and p50_latency > 0 and p95_latency / p50_latency > 3:
        observations.append(
            f"**Latency tail:** p95 latency ({p95_latency:.1f}s) is {p95_latency / p50_latency:.1f}× the median ({p50_latency:.1f}s). "
            "Inspect context size and individual cases; the all-record average mixes different tasks."
        )
    if int(df["has_error"].sum()):
        statuses = df.loc[df["has_error"], "response_status"].astype(str).value_counts().to_dict()
        observations.append(f"**Recorded errors:** {int(df['has_error'].sum())} record(s) are flagged. Status breakdown: {statuses}.")
    if task_count > 1:
        observations.append("**Scope caution:** multiple tasks are selected. Treat their scores as separate capability measures, not a shared leaderboard.")
    if len(versions_in_view) > 1:
        observations.append("**Schema caution:** records span multiple schema versions. Check metric semantics and field availability before pooling values.")
    zero_runs = []
    for metric_col in metric_columns:
        part = df.dropna(subset=[metric_col])
        if part.empty:
            continue
        per_run = part.groupby(["source_file", "run_id", "model_name"], dropna=False)[metric_col].agg(["mean", "count"]).reset_index()
        for _, rr in per_run[(per_run["mean"] == 0) & (per_run["count"] >= 5)].iterrows():
            zero_runs.append(f"{metric_label(metric_col)} = 0 for {int(rr['count'])} scored cases in {rr['model_name']} (run {str(rr['run_id'])[:8]}).")
    if zero_runs:
        observations.append("**Zero-score run(s):** " + " ".join(zero_runs[:3]) + " Inspect the cases and metric implementation before treating these as model capability alone.")
    if not observations:
        observations.append("No broad warning signal was detected. Narrow the view to one task and a metric for a more interpretable analysis.")
    for obs in observations[:5]:
        st.markdown(f"- {obs}")

# Main sections
overview_tab, findings_tab, capability_tab, efficiency_tab, cases_tab, quality_tab = st.tabs(
    ["Overview", "Findings & conclusions", "Capability & context", "Inference cost", "Case explorer", "Data quality"]
)

with overview_tab:
    st.markdown("#### Executive readout")
    if has_reference_analysis:
        st.markdown(
            "- **Negative retrieval:** the strict extraction prompt improves correct abstention on the matched 40-case sample, but exact retrieval of present facts remains weak.\n"
            "- **Long context:** in one Qwen3 0.6B NIAH run, lexical answer presence stays above 93% through 32K while instruction compliance drops to 16.7%; median latency grows from 5.28s to 19.01s.\n"
            "- **Needle position:** one 330-case Llama 3 8B NIAH run is much weaker at the opening edge than the middle.\n"
            "- **Comparison warning:** these are per-run observations. Different prompts, schemas, judge configuration and case overlap prevent a single cross-task model ranking."
        )
        st.caption("For the underlying run IDs, case counts, metrics and limitations, open **Findings & conclusions**.")
    else:
        st.info("The concise executive readout is tied to the supplied results.zip snapshot. Its reference runs are not all present in this results folder, so it is hidden to avoid presenting stale conclusions as current findings.")
    st.subheader("Metric comparison by task, model and schema")
    if not metric_columns:
        st.info("No numeric metrics are available in the selected records.")
    else:
        default_metric = "metric__lexical_exact_match" if "metric__lexical_exact_match" in metric_columns else metric_columns[0]
        selected_metric = st.selectbox("Metric", metric_columns, index=metric_columns.index(default_metric), format_func=metric_label, key="overview_metric")
        group_keys = ["benchmark", "experiment", "model_name", "schema_version"]
        grouped = df.groupby(group_keys, dropna=False)
        summary = grouped.agg(
            scored_cases=(selected_metric, "count"),
            cases=("case_id", "count"),
            runs=("run_id", "nunique"),
            mean_score=(selected_metric, "mean"),
            median_latency_sec=("latency_sec", "median"),
        ).reset_index()
        summary = summary.dropna(subset=["mean_score"])
        if not summary.empty:
            scale = 100 if is_percent_metric(selected_metric) else 1
            summary["score_display"] = summary["mean_score"] * scale
            summary["group_label"] = summary.apply(
                lambda r: f"{short_task(r['benchmark'], r['experiment'])} · {r['model_name']} · v{r['schema_version']}", axis=1
            )
            summary = summary.sort_values("score_display", ascending=True)
            fig = px.bar(
                summary,
                x="score_display",
                y="group_label",
                color="benchmark",
                orientation="h",
                text=summary["score_display"].map(lambda x: f"{x:.1f}%" if scale == 100 else f"{x:.3f}"),
                hover_data={
                    "scored_cases": True, "cases": True, "runs": True, "experiment": True,
                    "schema_version": True, "mean_score": ":.4f", "median_latency_sec": ":.2f", "score_display": False,
                },
                labels={"group_label": "Task · model · schema", "score_display": "Mean score (%)" if scale == 100 else f"Mean {metric_label(selected_metric)}"},
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            if scale == 100:
                fig.update_xaxes(range=[0, 108])
            fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=10))
            # Avoid creating an enormous plot when users select many schema/task combinations.
            plot_height = min(720, max(340, 30 * len(summary) + 100))
            st.plotly_chart(plot_layout(fig, plot_height), width="stretch")
            st.caption("Bars aggregate within task × model × schema, not across individual runs. Run settings and case sets may still differ; use Findings and the case explorer for controlled interpretation.")
        else:
            st.info("The selected metric has no numeric observations after filtering.")

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Dataset coverage")
        task_summary = df.groupby(["benchmark", "experiment"], dropna=False).agg(
            Records=("case_id", "size"), Runs=("run_id", "nunique"), Models=("model_name", "nunique")
        ).reset_index()
        task_summary["Task"] = task_summary.apply(lambda r: short_task(r["benchmark"], r["experiment"]), axis=1)
        st.dataframe(task_summary[["Task", "Records", "Runs", "Models"]], hide_index=True, width="stretch")
    with right:
        st.markdown("#### Metric availability")
        metric_rows = []
        for col in metric_columns:
            valid = pd.to_numeric(df[col], errors="coerce").dropna()
            metric_rows.append({"Metric": metric_label(col), "Scored records": len(valid), "Mean": nice_metric(float(valid.mean()), col) if not valid.empty else "—"})
        st.dataframe(pd.DataFrame(metric_rows), hide_index=True, width="stretch", height=280)

with findings_tab:
    st.subheader("Findings and conclusions from the supplied archive")
    st.caption("The archive-wide section uses all JSONL files found under the selected results directory, regardless of sidebar filters. Case-study numbers are calculated from named runs so they remain auditable.")

    # Archive-wide inventory
    schema_counts = all_df.groupby("schema_version").size().rename("Records").reset_index().sort_values("schema_version")
    task_counts = all_df.groupby(["benchmark", "experiment"], dropna=False).size().rename("Records").reset_index()
    task_counts["Task"] = task_counts.apply(lambda r: short_task(r["benchmark"], r["experiment"]), axis=1)
    task_counts = task_counts.sort_values("Records", ascending=False)
    total_keys = int(all_df["case_key"].notna().sum()) if "case_key" in all_df else 0
    unique_keys = int(all_df.loc[all_df["case_key"].notna(), "case_key"].astype(str).nunique()) if total_keys else 0
    whole_lat = pd.to_numeric(all_df["latency_sec"], errors="coerce").dropna()
    total_runs = all_df[["source_file", "run_id"]].drop_duplicates().shape[0]
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Loaded records", f"{len(all_df):,}")
    f2.metric("JSONL files / runs", f"{total_runs:,}")
    f3.metric("Distinct task designs", f"{len(task_counts):,}")
    f4.metric("Distinct case keys", f"{unique_keys:,}" if total_keys else "Not recorded")
    st.success(f"JSONL parsing: {len(all_df):,} records loaded from {len(files):,} files with {len(diagnostics):,} malformed/read-shape issue(s).")
    st.markdown("#### What the archive contains")
    ctask, cschema = st.columns([1.3, 1])
    with ctask:
        st.dataframe(task_counts[["Task", "Records"]], hide_index=True, width="stretch")
    with cschema:
        st.dataframe(schema_counts, hide_index=True, width="stretch")
    if total_keys and unique_keys < total_keys:
        st.info(f"{total_keys:,} records carry `case_key` values but map to {unique_keys:,} distinct keys. These include repeated cases from reruns or prompt variants; {len(all_df):,} records should not be described as {len(all_df):,} independent test cases.")

    if not whole_lat.empty:
        p50_all, p95_all = float(whole_lat.median()), float(whole_lat.quantile(.95))
        st.markdown("#### Inference cost: archive-wide context")
        lc1, lc2, lc3, lc4 = st.columns(4)
        lc1.metric("Median end-to-end latency", f"{p50_all:.2f}s")
        lc2.metric("Mean end-to-end latency", f"{whole_lat.mean():.2f}s")
        lc3.metric("P95 end-to-end latency", f"{p95_all:.2f}s")
        lc4.metric("P95 / median", f"{p95_all / p50_all:.1f}×" if p50_all > 0 else "—")
        st.caption("This overall latency summary mixes contexts and task designs. Use the per-run context tables below for interpretation; do not read it as a model-only speed comparison.")

    # Prompt experiment: matched 40 case keys across baseline and stricter prompt runs.
    st.markdown("#### Finding 1 — A strict extraction prompt improves abstention, but answerable retrieval remains weak")
    prompt_runs = [
        ("b0ee1fb9c668", "Baseline · 0.6B judge"),
        ("bd41b94deb6e", "Strict prompt · 0.6B judge"),
        ("54c6c18eeebc", "Strict prompt · 4B judge"),
    ]
    prompt_rows = []
    prompt_chart_rows = []
    for rid, label in prompt_runs:
        rg = run_rows(all_df, rid)
        metric = "metric__answerability_exact_match"
        if rg.empty or metric not in rg:
            continue
        valid_score = pd.to_numeric(rg[metric], errors="coerce").dropna()
        ans_score = class_score(rg, True)
        unans_score = class_score(rg, False)
        prompt_rows.append({
            "Variant": label, "Run": rid, "Cases": len(rg),
            "Exact match overall": f"{valid_score.mean():.1%}" if not valid_score.empty else "—",
            "Answerable retrieval": f"{ans_score:.1%}" if ans_score is not None else "—",
            "Correct abstention": f"{unans_score:.1%}" if unans_score is not None else "—",
            "Median latency": f"{rg['latency_sec'].median():.2f}s",
            "P95 latency": f"{rg['latency_sec'].quantile(.95):.2f}s",
        })
        for cls, value in [("Answerable cases", ans_score), ("Unanswerable cases", unans_score)]:
            if value is not None:
                prompt_chart_rows.append({"Prompt variant": label, "Case class": cls, "Correct (%)": value * 100})
    if prompt_rows:
        st.dataframe(pd.DataFrame(prompt_rows), hide_index=True, width="stretch")
        if prompt_chart_rows:
            pfig = px.bar(
                pd.DataFrame(prompt_chart_rows), x="Prompt variant", y="Correct (%)", color="Case class", barmode="group",
                text=pd.DataFrame(prompt_chart_rows)["Correct (%)"].map(lambda x: f"{x:.0f}%"),
                labels={"Correct (%)": "Answerability exact match (%)"},
            )
            pfig.update_traces(textposition="outside", cliponaxis=False)
            pfig.update_yaxes(range=[0, 112])
            st.plotly_chart(plot_layout(pfig, 350), width="stretch")
        base_run = run_rows(all_df, "b0ee1fb9c668")
        strict_run = run_rows(all_df, "bd41b94deb6e")
        if not base_run.empty and not strict_run.empty:
            base_map = base_run.dropna(subset=["case_key"]).drop_duplicates("case_key").set_index("case_key")
            strict_map = strict_run.dropna(subset=["case_key"]).drop_duplicates("case_key").set_index("case_key")
            common = sorted(set(base_map.index) & set(strict_map.index))
            if common:
                st.markdown(
                    f"**Interpretation:** the two 40-case runs share {len(common)} case keys. On that shared case set, the baseline recorded "
                    f"{base_map.loc[common, 'metric__answerability_exact_match'].mean():.1%} exact match, while the strict prompt recorded "
                    f"{strict_map.loc[common, 'metric__answerability_exact_match'].mean():.1%}. Correct abstention moved from "
                    f"{class_score(base_map.loc[common].reset_index(), False):.1%} to {class_score(strict_map.loc[common].reset_index(), False):.1%}, "
                    f"but exact retrieval on answerable cases remained at {class_score(strict_map.loc[common].reset_index(), True):.1%}. The strongest observed benefit is refusal when evidence is absent, not retrieval when evidence is present."
                )
                with_judge = run_rows(all_df, "54c6c18eeebc")
                if not with_judge.empty:
                    judge_map = with_judge.dropna(subset=["case_key"]).drop_duplicates("case_key").set_index("case_key")
                    common_judge = sorted(set(strict_map.index) & set(judge_map.index))
                    equal_predictions = sum(str(strict_map.loc[k, "predicted"]) == str(judge_map.loc[k, "predicted"]) for k in common_judge)
                    st.caption(f"The strict-prompt runs scored with different judge-model configurations share {len(common_judge)} case keys and have identical saved predictions on {equal_predictions}/{len(common_judge)}. The judge changed from Qwen3 0.6B to Qwen3 4B, and the saved generations differ on some cases, so do not attribute the small score difference to the evaluator alone.")
    else:
        st.info("The named negative-retrieval case-study runs are not present in the configured results folder.")

    st.markdown("#### Finding 1b — More context did not rescue the baseline negative-retrieval run")
    extended_negative = []
    for rid, label in [
        ("a46a1ab0866e", "Strict prompt · 4K/8K · 80 cases"),
        ("45c286ad0e18", "Baseline prompt · 4K–32K · 160 cases"),
    ]:
        rg = run_rows(all_df, rid).copy()
        if rg.empty:
            continue
        overall = (
            pd.to_numeric(rg["metric__answerability_exact_match"], errors="coerce").dropna()
            if "metric__answerability_exact_match" in rg.columns else pd.Series(dtype=float)
        )
        ans_score = class_score(rg, True)
        abstain_score = class_score(rg, False)
        extended_negative.append({
            "Run": label,
            "Cases": len(rg),
            "Answerability exact match": f"{overall.mean():.1%}" if not overall.empty else "—",
            "Answerable retrieval": f"{ans_score:.1%}" if ans_score is not None else "—",
            "Correct abstention": f"{abstain_score:.1%}" if abstain_score is not None else "—",
            "Median latency": f"{rg['latency_sec'].median():.2f}s",
            "P95 latency": f"{rg['latency_sec'].quantile(.95):.2f}s",
        })
        if rid == "45c286ad0e18" and "metric__answerability_exact_match" in rg:
            rg["Context (k tokens)"] = (pd.to_numeric(rg["context_length"], errors="coerce") / 1000).round().astype("Int64")
            context_rows = rg.groupby("Context (k tokens)", dropna=False).agg(
                Cases=("case_id", "size"),
                Exact_match=("metric__answerability_exact_match", "mean"),
                Median_latency=("latency_sec", "median"),
            ).reset_index()
            context_rows["Answerability exact match"] = context_rows.pop("Exact_match").map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
            context_rows["Median latency"] = context_rows.pop("Median_latency").map(lambda x: f"{x:.2f}s" if pd.notna(x) else "—")
            st.markdown("**Baseline prompt by context size**")
            st.dataframe(context_rows, hide_index=True, width="stretch")
    if extended_negative:
        st.dataframe(pd.DataFrame(extended_negative), hide_index=True, width="stretch")
        st.markdown("**Conclusion:** the 80-case strict-prompt run still retrieves only 12.5% of answerable facts, although it abstains correctly on 82.5% of unanswerable cases. In the 160-case baseline run, answerability exact match is 0% at every tested context bucket; median latency jumps to 65.68s at 32K. Increasing context alone did not correct this baseline failure.")
        st.caption("These are different runs with different context mixes and prompt setups; treat this as diagnostic evidence, not a causal prompt-only or model-size comparison.")
    else:
        st.info("The extended negative-retrieval runs are not present in this results folder.")

    st.markdown("#### Finding 2 — Qwen3 0.6B retains answer accuracy into 32K, but output-format compliance falls sharply")
    qwen_ctx = run_rows(all_df, "478efbee30ab")
    if not qwen_ctx.empty:
        qwen_ctx["context_k"] = (pd.to_numeric(qwen_ctx["context_length"], errors="coerce") / 1000).round().astype("Int64")
        agg_spec = {"Cases": ("case_id", "size"), "Median latency (s)": ("latency_sec", "median")}
        for c in ["metric__lexical_exact_match", "metric__instruction_compliance", "metric__llm_judge"]:
            if c in qwen_ctx.columns:
                agg_spec[metric_label(c)] = (c, "mean")
        ctx_table = qwen_ctx.groupby("context_k", dropna=False).agg(**agg_spec).reset_index().rename(columns={"context_k": "Context (k tokens)"})
        for col in [metric_label(c) for c in ["metric__lexical_exact_match", "metric__instruction_compliance", "metric__llm_judge"] if c in qwen_ctx.columns]:
            if col in ctx_table.columns:
                ctx_table[col] = ctx_table[col].map(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
        ctx_table["Median latency (s)"] = ctx_table["Median latency (s)"].map(lambda v: f"{v:.2f}s" if pd.notna(v) else "—")
        st.dataframe(ctx_table, hide_index=True, width="stretch")
        qfig_df = qwen_ctx.groupby("context_k", dropna=False).agg(
            **{"Lexical exact match": ("metric__lexical_exact_match", "mean"), "Instruction compliance": ("metric__instruction_compliance", "mean")}
        ).reset_index().melt(id_vars="context_k", var_name="Measure", value_name="Score")
        qfig_df["Score"] *= 100
        qfig = px.line(qfig_df, x="context_k", y="Score", color="Measure", markers=True, labels={"context_k": "Context length (k tokens)", "Score": "Mean score (%)"})
        qfig.update_traces(line_width=2.5, marker_size=8)
        qfig.update_yaxes(range=[0, 105])
        st.plotly_chart(plot_layout(qfig, 350), width="stretch")
        st.markdown("**Conclusion:** in this 90-case saved run, lexical exact match changes from 100.0% at ~8K to 96.7% at ~16K and 93.3% at ~32K, while median latency increases from 5.28s to 8.56s and 19.01s. Instruction compliance drops to 16.7% at ~32K. Answer presence and strict instruction following are different outcomes here.")
    else:
        st.info("The Qwen3 0.6B NIAH context-sensitivity run is not present in the configured results folder.")

    st.markdown("#### Finding 3 — Llama 3 8B shows a strong position effect in its 330-case NIAH run")
    llama_depth = run_rows(all_df, "2bfcd3f32b11")
    if not llama_depth.empty:
        ld = llama_depth.dropna(subset=["depth", "metric__lexical_exact_match"]).groupby("depth").agg(
            Cases=("case_id", "size"), Exact_match=("metric__lexical_exact_match", "mean"),
            Judge=("metric__llm_judge", "mean"), Median_latency=("latency_sec", "median"),
        ).reset_index()
        display_ld = ld.copy()
        display_ld["Depth (%)"] = (display_ld.pop("depth") * 100).round().astype(int)
        display_ld["Exact match"] = display_ld.pop("Exact_match").map(lambda v: f"{v:.1%}")
        display_ld["LLM judge"] = display_ld.pop("Judge").map(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
        display_ld["Median latency"] = display_ld.pop("Median_latency").map(lambda v: f"{v:.2f}s" if pd.notna(v) else "—")
        st.dataframe(display_ld[["Depth (%)", "Cases", "Exact match", "LLM judge", "Median latency"]], hide_index=True, width="stretch")
        ldfig = px.line(ld.assign(depth_percent=(ld["depth"] * 100)), x="depth_percent", y=ld["Exact_match"], markers=True,
                        labels={"depth_percent": "Needle depth in context (%)", "Exact_match": "Lexical exact match (%)"})
        ldfig.update_traces(line_width=3, marker_size=8)
        ldfig.update_yaxes(range=[0, 1.05], tickformat=".0%")
        # `Exact_match` is a 0-1 score, so the percentage axis uses a fraction formatter.
        st.plotly_chart(plot_layout(ldfig, 350, legend=False), width="stretch")
        st.markdown("**Conclusion:** on 30 cases per depth, exact match is 6.7% at the opening edge, rises to 96.7% at 40–50% depth, and falls to 63.3% at the final edge. This is evidence of position sensitivity in this run—not a universal statement about every model or context size.")
    else:
        st.info("The 330-case Llama 3 8B NIAH run is not present in the configured results folder.")

    st.markdown("#### Finding 4 — Larger Qwen3 4B runs score highly on distractor and multihop tasks, with a latency cost")
    run_defs = [
        ("aadb46540671", "NIAH distractor · Qwen3 4B"),
        ("63b9fdb9f911", "NIAH multihop · Qwen3 4B"),
        ("54630557c081", "NIAH multihop · Qwen3 0.6B"),
    ]
    comp_rows = []
    present_comp_ids = set()
    for rid, label in run_defs:
        rg = run_rows(all_df, rid)
        if rg.empty:
            continue
        present_comp_ids.add(rid)
        comp_rows.append({
            "Run": label, "Cases": len(rg),
            "Context range": f"{rg['context_length'].min()/1000:.0f}–{rg['context_length'].max()/1000:.0f}K" if rg["context_length"].notna().any() else "—",
            "Lexical exact match": f"{rg['metric__lexical_exact_match'].mean():.1%}" if rg["metric__lexical_exact_match"].notna().any() else "—",
            "Instruction compliance": f"{rg['metric__instruction_compliance'].mean():.1%}" if rg["metric__instruction_compliance"].notna().any() else "—",
            "LLM judge": f"{rg['metric__llm_judge'].mean():.1%}" if rg["metric__llm_judge"].notna().any() else "—",
            "Median latency": f"{rg['latency_sec'].median():.2f}s",
            "P95 latency": f"{rg['latency_sec'].quantile(.95):.2f}s",
        })
    if comp_rows:
        st.dataframe(pd.DataFrame(comp_rows), hide_index=True, width="stretch")
        if present_comp_ids == {rid for rid, _ in run_defs}:
            st.markdown("**Conclusion:** the saved Qwen3 4B distractor run has 100% lexical exact match on 60 cases; its multihop run has 100% lexical exact match on 120 cases and 98.3% instruction compliance. In the multihop runs, median latency is 45.45s for Qwen3 4B versus 2.43s for Qwen3 0.6B, but only 6 case keys overlap between those run files. Treat this as descriptive evidence, not a controlled head-to-head comparison.")
        else:
            st.caption("Some reference runs from the supplied archive are absent. The table shows only runs found; the canned comparison conclusion is withheld.")
    else:
        st.info("The named Qwen3 4B task runs are not present in the configured results folder.")

    st.markdown("#### Finding 5 — Metric semantics and metadata need explicit checks")
    sample_metric = run_rows(all_df, "478efbee30ab")
    if not sample_metric.empty and "metric__instruction_compliance" in sample_metric:
        example_mask = (
            sample_metric["metric__lexical_exact_match"].eq(1)
            & sample_metric["metric__instruction_compliance"].eq(0)
            & sample_metric["predicted"].notna()
        )
        examples = sample_metric[example_mask]
        if not examples.empty:
            ex = examples.iloc[0]
            st.warning(
                "In the saved NIAH outputs, `lexical_exact_match` can equal 1.0 when the prediction contains the expected code inside extra prose, "
                "while `instruction_compliance` is 0.0. Therefore the displayed lexical metric should not be interpreted as strict whole-string equality or format compliance. "
                "Audit the metric implementation and keep answer correctness separate from response-format adherence."
            )
            ec1, ec2 = st.columns(2)
            with ec1:
                st.markdown("**Expected answer**")
                st.code(str(ex["expected"]))
            with ec2:
                st.markdown("**Example prediction**")
                pred = str(ex["predicted"])
                st.code(pred[:900] + ("…" if len(pred) > 900 else ""))
    status_counts = all_df["response_status"].astype(str).value_counts()
    if "unknown" in status_counts.index or "evaluation_error" in status_counts.index:
        st.info(
            f"Status metadata: {int(status_counts.get('unknown', 0))} records have unknown/missing status and "
            f"{int(status_counts.get('evaluation_error', 0))} record has `evaluation_error`. The dashboard now counts evaluation errors in its error KPI; unknown status is reported separately."
        )
    if total_keys:
        st.caption(f"Case identity coverage: {total_keys:,}/{len(all_df):,} records have a `case_key`, covering {unique_keys:,} unique keys. Older records without case keys cannot be robustly deduplicated by key.")

    st.markdown("#### Overall conclusions and recommended next experiments")
    st.markdown(
        "**What the current evidence supports**\n"
        "- Treat negative retrieval as two distinct abilities: retrieving facts that are present and abstaining when evidence is absent. The strict prompt improved the second much more than the first in the matched sample.\n"
        "- Treat context length as a joint quality/latency/format trade-off. The Qwen3 0.6B NIAH run remained strong on answer presence at 32K, but response-format adherence fell sharply and latency increased.\n"
        "- Include needle position in NIAH reporting; a single average can hide poor performance near the beginning or end of context.\n"
        "- Keep latency numbers task- and context-specific. The archive-wide p95 is 10.7× the median, but the pooled statistic mixes very different tasks and model settings.\n"
        "- Audit metric definitions before using the word *exact*: saved outputs show lexical exact match can be 1.0 even when the response includes extra prose and instruction compliance is 0.0.\n\n"
        "**Next experiments**\n"
        "1. Run paired model comparisons over identical `case_key` values, prompts, context lengths, generation settings, hardware and seeds.\n"
        "2. For negative retrieval, report answerable exact retrieval, correct abstention and format compliance separately.\n"
        "3. Verify `lexical_exact_match` implementation and add a separate strict whole-response exact-match metric if that is the intended requirement.\n"
        "4. Save generator and judge configurations as separate metadata; do not attribute differences to the judge when saved predictions also changed.\n"
        "5. Report denominators and uncertainty alongside scores, especially for small runs (for example, the six-record Llama 3.2 1B sample)."
    )
    archive_report = Path(__file__).with_name("ARCHIVE_FINDINGS.md")
    if has_reference_analysis and archive_report.is_file():
        st.download_button(
            "Download supplied-archive findings (Markdown)",
            data=archive_report.read_text(encoding="utf-8"),
            file_name="probebench_archive_findings.md",
            mime="text/markdown",
            width="content",
        )
    elif archive_report.is_file():
        st.caption("The bundled archive report describes the originally supplied results.zip and is not offered as a report for this different results folder.")

with capability_tab:
    st.subheader("Context sensitivity and retrieval position")
    st.markdown("Select one run at a time. This avoids 38 overlapping lines and a legend full of long file names.")
    usable_metric_columns = [c for c in metric_columns if df[c].notna().any()]
    if not usable_metric_columns:
        st.info("No numeric metrics to plot.")
    else:
        default_metric = "metric__lexical_exact_match" if "metric__lexical_exact_match" in usable_metric_columns else usable_metric_columns[0]
        selected_metric = st.selectbox("Metric to analyse", usable_metric_columns, index=usable_metric_columns.index(default_metric), format_func=metric_label, key="capability_metric")
        metric_view = df.dropna(subset=[selected_metric]).copy()
        catalog = run_catalog(metric_view, selected_metric)
        if metric_view.empty or catalog.empty:
            st.info("No values for this metric in the current selection.")
        else:
            chosen_key = st.selectbox("Run to inspect", catalog["run_key"].tolist(), format_func=lambda k: catalog.loc[catalog["run_key"].eq(k), "run_label"].iloc[0], key="capability_run")
            selected_run = metric_view[metric_view["run_key"].eq(chosen_key)].copy()
            selected_run["score_display"] = selected_run[selected_metric] * (100 if is_percent_metric(selected_metric) else 1)
            selected_run["context_k"] = (pd.to_numeric(selected_run["context_length"], errors="coerce") / 1000).round().astype("Int64")
            selected_run["depth_bucket"] = (pd.to_numeric(selected_run["depth"], errors="coerce") * 20).round() / 20
            selected_run["depth_percent"] = selected_run["depth_bucket"] * 100
            a, b = st.columns(2)
            with a:
                st.markdown("#### Score vs. context length")
                ctx = selected_run.dropna(subset=["context_k"]).groupby("context_k", dropna=False).agg(
                    score=("score_display", "mean"), cases=("case_id", "count"), median_latency=("latency_sec", "median")
                ).reset_index()
                if ctx.empty:
                    st.info("Context length is not recorded in this run.")
                else:
                    fig = px.line(ctx, x="context_k", y="score", markers=True, hover_data={"cases": True, "median_latency": ":.2f"},
                                  labels={"context_k": "Context length (k tokens)", "score": f"Mean {metric_label(selected_metric)}" + (" (%)" if is_percent_metric(selected_metric) else "")})
                    fig.update_traces(line_width=3, marker_size=8)
                    st.plotly_chart(plot_layout(fig, 390, legend=False), width="stretch")
            with b:
                st.markdown("#### Score vs. needle position")
                dep = selected_run.dropna(subset=["depth_percent"]).groupby("depth_percent", dropna=False).agg(
                    score=("score_display", "mean"), cases=("case_id", "count")
                ).reset_index()
                if dep.empty:
                    st.info("Retrieval depth is not recorded in this run.")
                else:
                    fig = px.line(dep, x="depth_percent", y="score", markers=True, hover_data={"cases": True},
                                  labels={"depth_percent": "Needle depth in context (%)", "score": f"Mean {metric_label(selected_metric)}" + (" (%)" if is_percent_metric(selected_metric) else "")})
                    fig.update_traces(line_width=3, marker_size=8)
                    st.plotly_chart(plot_layout(fig, 390, legend=False), width="stretch")
            st.markdown("#### Context × depth heatmap")
            heat = selected_run.dropna(subset=["context_k", "depth_percent"]).pivot_table(
                index="depth_percent", columns="context_k", values="score_display", aggfunc="mean"
            )
            if not heat.empty:
                heat = heat.sort_index()
                fig = px.imshow(heat, aspect="auto", text_auto=".1f", color_continuous_scale="Tealgrn",
                                labels={"x": "Context length (k tokens)", "y": "Needle depth (%)", "color": "Mean score"})
                st.plotly_chart(plot_layout(fig, 360, legend=False), width="stretch")
            st.caption("Context values are rounded to the nearest 1K tokens and realised depth to the nearest 5 percentage points for readability. Hover for case counts. This is an exploratory view of the selected run, not a cross-run ranking.")

with efficiency_tab:
    st.subheader("Latency, generation speed and tail behaviour")
    latency_values = pd.to_numeric(df["latency_sec"], errors="coerce").dropna()
    tps_values = pd.to_numeric(df["output_tokens_per_sec"], errors="coerce").dropna()
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Median latency", f"{latency_values.median():.2f}s" if not latency_values.empty else "—")
    e2.metric("Mean latency", f"{latency_values.mean():.2f}s" if not latency_values.empty else "—")
    e3.metric("P95 latency", f"{latency_values.quantile(.95):.2f}s" if not latency_values.empty else "—")
    e4.metric("Median output tok/s", f"{tps_values.median():.2f}" if not tps_values.empty else "—")
    tasks_for_latency = df["task_label"].value_counts().index.tolist()
    default_task = tasks_for_latency[0] if tasks_for_latency else None
    if default_task:
        chosen_task = st.selectbox("Task for charts", tasks_for_latency, index=0, format_func=lambda x: short_task(*x.split(" / ", 1)) if " / " in x else x, key="latency_task")
        latency_df = df[df["task_label"].eq(chosen_task)].dropna(subset=["latency_sec"]).copy()
    else:
        latency_df = df.dropna(subset=["latency_sec"]).copy()
    l1, l2 = st.columns(2)
    with l1:
        st.markdown("#### Latency distribution by model")
        if not latency_df.empty:
            fig = px.box(latency_df, x="model_name", y="latency_sec", color="model_name", points="outliers",
                         hover_data=["run_id", "source_label", "context_length", "depth", "case_id"],
                         labels={"model_name": "Model", "latency_sec": "End-to-end latency (s)"})
            fig.update_layout(showlegend=False)
            st.plotly_chart(plot_layout(fig, 420, legend=False), width="stretch")
        else:
            st.info("No latency data for this task.")
    with l2:
        st.markdown("#### Context length vs. latency")
        scatter_df = latency_df.dropna(subset=["context_length"]).copy()
        if not scatter_df.empty:
            fig = px.scatter(scatter_df, x="context_length", y="latency_sec", color="model_name", hover_data=["run_id", "source_label", "depth", "case_id", "response_status"],
                             labels={"context_length": "Context length (tokens)", "latency_sec": "Latency (s)", "model_name": "Model"}, opacity=0.72)
            st.plotly_chart(plot_layout(fig, 420), width="stretch")
        else:
            st.info("Need both context length and latency to draw this chart.")
    st.markdown("#### Generation speed vs. generated-token count")
    speed_df = latency_df.dropna(subset=["output_tokens_per_sec", "eval_count"]).copy()
    if not speed_df.empty:
        fig = px.scatter(speed_df, x="eval_count", y="output_tokens_per_sec", color="model_name", hover_data=["context_length", "latency_sec", "run_id", "case_id"],
                         labels={"eval_count": "Generated tokens", "output_tokens_per_sec": "Output tokens / second", "model_name": "Model"}, opacity=0.7)
        st.plotly_chart(plot_layout(fig, 360), width="stretch")
    else:
        st.info("Generation speed requires both `eval_count` and `eval_duration_ns`; those fields are not present in enough records for this task.")
    st.caption("Charts are scoped to one task to avoid mixing unrelated workloads. Latency includes end-to-end response latency; output tok/s uses eval_count ÷ eval_duration_ns. Do not compare speed across hardware or generation configurations without accounting for those differences.")

with cases_tab:
    st.subheader("Case-level result inspection")
    st.markdown("Inspect one saved response at a time. Expected and predicted strings are shown from the original JSONL record.")
    case_view = df.copy()
    if metric_columns:
        case_metric = st.selectbox("Metric column in table", ["(none)"] + metric_columns, format_func=lambda v: "No metric" if v == "(none)" else metric_label(v), key="case_metric")
    else:
        case_metric = "(none)"
    display_columns = [
        "source_label", "schema_version", "run_id", "benchmark", "experiment", "model_name", "case_id",
        "context_length", "depth", "response_status", "has_error", "latency_sec", "expected", "predicted"
    ]
    if case_metric != "(none)":
        display_columns.append(case_metric)
    display_columns = [c for c in display_columns if c in case_view.columns]
    st.dataframe(case_view[display_columns], width="stretch", hide_index=True, height=390)
    st.markdown("#### Inspect one case")
    case_options = list(range(len(df)))
    labels = [f"{row['model_name']} · {str(row['run_id'])[:8]} · line {int(row['line_number'])}" for _, row in df.iterrows()]
    selection = st.selectbox("Case", case_options, format_func=lambda i: labels[i], key="case_selection")
    selected_row = df.iloc[int(selection)]
    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.markdown("**Question**")
        st.write(selected_row.get("question") or "No question field in this schema/run.")
        st.markdown("**Expected**")
        st.code(str(selected_row.get("expected") if pd.notna(selected_row.get("expected")) else "Not recorded"))
    with detail_right:
        st.markdown("**Predicted**")
        st.code(str(selected_row.get("predicted") if pd.notna(selected_row.get("predicted")) else "Not recorded"))
        st.markdown("**Response status / error**")
        st.write(f"{selected_row.get('response_status')} / {selected_row.get('error') or 'No recorded error'}")
    with st.expander("View original JSON record"):
        st.json(selected_row["_raw_record"])

with quality_tab:
    st.subheader("Schema coverage and run integrity")
    q1, q2 = st.columns(2)
    with q1:
        st.markdown("#### Records by schema version")
        version_summary = df.groupby("schema_version", dropna=False).size().reset_index(name="records")
        fig = px.bar(version_summary, x="schema_version", y="records", color="schema_version", labels={"schema_version": "Schema version", "records": "Records"})
        st.plotly_chart(plot_layout(fig, 320, legend=False), width="stretch")
        st.markdown("#### Response status")
        status_summary = df.groupby("response_status", dropna=False).size().reset_index(name="records")
        fig = px.pie(status_summary, names="response_status", values="records", hole=.62)
        st.plotly_chart(plot_layout(fig, 320), width="stretch")
    with q2:
        st.markdown("#### Missing-field coverage")
        coverage_fields = ["case_id", "case_key", "context_tokens", "target_tokens", "depth", "num_ctx", "prompt_eval_count", "latency_sec", "expected", "predicted"] + metric_columns
        coverage = []
        for col in coverage_fields:
            missing = int(df[col].isna().sum()) if col in df.columns else len(df)
            label = metric_label(col) if col.startswith("metric__") else col.replace("_", " ").title()
            coverage.append({"Field": label, "Missing rows": missing, "Missing %": 100 * missing / len(df) if len(df) else 0})
        coverage_df = pd.DataFrame(coverage).sort_values("Missing %", ascending=False)
        fig = px.bar(coverage_df, x="Missing %", y="Field", orientation="h", color="Missing %", color_continuous_scale="Tealgrn", range_x=[0, 100])
        st.plotly_chart(plot_layout(fig, max(360, min(640, 26 * len(coverage_df) + 100)), legend=False), width="stretch")
        st.markdown("#### Error records")
        errors_df = df[df["has_error"]][["source_label", "line_number", "run_id", "case_id", "response_status", "error"]]
        if errors_df.empty:
            st.success("No error or evaluation-error statuses were recorded in the selected rows.")
        else:
            st.dataframe(errors_df, hide_index=True, width="stretch")
        missing_status_df = df[df["response_status"].astype(str).str.lower().eq("unknown")][["source_label", "line_number", "run_id", "case_id", "schema_version"]]
        if not missing_status_df.empty:
            with st.expander(f"Records with unknown response status ({len(missing_status_df)})"):
                st.dataframe(missing_status_df, hide_index=True, width="stretch")

    st.markdown("#### Context configuration checks")
    context_check = df.dropna(subset=["prompt_eval_count", "num_ctx"]).copy()
    if context_check.empty:
        st.info("No records contain both prompt_eval_count and generation.num_ctx.")
    else:
        exceeds = context_check[context_check["prompt_eval_exceeds_num_ctx"] == True]
        ratio = len(exceeds) / len(context_check)
        st.metric("Prompt tokens greater than recorded num_ctx", f"{len(exceeds):,} / {len(context_check):,} ({ratio:.1%})")
        if not exceeds.empty:
            st.warning(
                "In these records, response.prompt_eval_count exceeds generation.num_ctx. This may reflect dynamic runtime settings, context shifting, or a logging/configuration mismatch; verify the runner's effective context configuration."
            )
            ctx_summary = context_check.groupby(["source_label", "model_name", "num_ctx"], dropna=False).agg(
                cases=("case_id", "count"), prompt_eval_mean=("prompt_eval_count", "mean"),
                greater_than_num_ctx=("prompt_eval_exceeds_num_ctx", "sum"), max_ratio=("prompt_eval_to_num_ctx_ratio", "max"),
            ).reset_index()
            ctx_summary["prompt_eval_mean"] = ctx_summary["prompt_eval_mean"].round(0)
            ctx_summary["max_ratio"] = ctx_summary["max_ratio"].map(lambda v: f"{v:.2f}×" if pd.notna(v) else "—")
            ctx_summary["greater_than_num_ctx"] = ctx_summary["greater_than_num_ctx"].astype(int)
            st.dataframe(ctx_summary, hide_index=True, width="stretch")
        else:
            st.success(f"No prompt token count exceeds its recorded num_ctx in the {len(context_check):,} records with both fields.")

    st.markdown("#### File parsing diagnostics")
    selected_paths = set(df["source_file"].astype(str).unique())
    diagnostics_in_view = [d for d in diagnostics if str(d.get("file", "")) in selected_paths]
    if diagnostics_in_view:
        st.warning(f"{len(diagnostics_in_view)} issue(s) occurred while reading selected files. Valid rows remain available; malformed lines were not counted as cases.")
        st.dataframe(pd.DataFrame(diagnostics_in_view), hide_index=True, width="stretch")
    else:
        st.success("No JSON parsing or record-shape issues were detected in the selected files.")

st.divider()
st.markdown(
    '<div class="small-muted">Probebench Evaluation Lab · Local analysis only · JSONL files are read from disk and are not uploaded by this dashboard.</div>',
    unsafe_allow_html=True,
)
