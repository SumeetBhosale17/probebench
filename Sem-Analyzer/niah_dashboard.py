"""
NIAH (Needle-in-a-Haystack) Evaluation Dashboard
=================================================
A Streamlit dashboard for analyzing long-range dependency / retrieval
experiments on LLMs.

Beyond the raw exact-match flag your harness produces, this app scores
each response on two axes:

  1. LEXICAL match   - does the exact "needle" (e.g. ALPHA-9921-X) appear
                        anywhere in the model's output?
  2. SEMANTIC/LOGICAL correctness - does the model actually *assert* that
                        code as the answer, or does it find the right
                        string but then talk itself out of it ("this looks
                        like a glitch/placeholder"), or hallucinate an
                        entirely unrelated answer from the surrounding text?

Run with:
    pip install -r requirements.txt
    streamlit run niah_dashboard.py
"""

import io
import os
import re
import json
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="NIAH Evaluation Dashboard",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# Root .env / results file config
# ----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
ENV_PATH = REPO_ROOT / ".env"

# ----------------------------------------------------------------------------
# Correctness taxonomy
# ----------------------------------------------------------------------------
# A "code" is any needle payload shaped like ALPHA-9921-X / 8829-BETA-Z / etc.
CODE_PATTERN = re.compile(r"\b[A-Z0-9]+(?:-[A-Z0-9]+){1,}\b")

DENIAL_PATTERNS = re.compile(
    r"(no important secret|no specific secret|does not (contain|mention)|"
    r"doesn't (contain|mention)|not part of the actual|no mention of|"
    r"\bglitch\b|\bplaceholder\b|red herring|there is no\b|"
    r"none, there is|not explicitly mention|does not appear to)",
    re.IGNORECASE,
)

CATEGORY_ORDER = [
    "Exact / Clean Match",
    "Correct (Verbose)",
    "Correct but Denied/Confused",
    "Hallucinated / Wrong",
    "Unscored",
]

CATEGORY_COLORS = {
    "Exact / Clean Match": "#1a9850",
    "Correct (Verbose)": "#66bd63",
    "Correct but Denied/Confused": "#fee08b",
    "Hallucinated / Wrong": "#d73027",
    "Unscored": "#999999",
}


def extract_codes(text: str):
    if not isinstance(text, str):
        return []
    return CODE_PATTERN.findall(text.upper())


def normalize(s) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(s).upper())


def classify_row(needle: str, predicted: str):
    """Return (category, lexical_ok, semantic_ok, needle_code)."""
    needle_codes = extract_codes(needle)
    needle_code = needle_codes[-1] if needle_codes else None

    if needle_code is None:
        return "Unscored", False, False, None

    pred_codes = extract_codes(predicted)
    contains_code = needle_code in pred_codes
    clean_match = normalize(predicted) == needle_code
    denied = bool(DENIAL_PATTERNS.search(str(predicted))) if isinstance(predicted, str) else False

    if contains_code and clean_match:
        category = "Exact / Clean Match"
    elif contains_code and not denied:
        category = "Correct (Verbose)"
    elif contains_code and denied:
        category = "Correct but Denied/Confused"
    else:
        category = "Hallucinated / Wrong"

    lexical_ok = contains_code
    # "Denied" rows found the right text but the model's own reasoning
    # rejects it as the answer -- that's a logic failure, not a success,
    # even though the substring is technically present.
    semantic_ok = category in ("Exact / Clean Match", "Correct (Verbose)")
    return category, lexical_ok, semantic_ok, needle_code


def read_env_value(env_path: Path, key: str) -> str | None:
    if not env_path.exists():
        return None

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").strip()

        env_key, sep, env_value = stripped.partition("=")
        if sep and env_key.strip() == key:
            value = env_value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            return value

    return None


def get_result_file_path() -> Path:
    result_file_path = read_env_value(ENV_PATH, "RESULT_FILE_PATH")
    if not result_file_path:
        st.error(f"Set RESULT_FILE_PATH in {ENV_PATH} to the results CSV path.")
        st.stop()

    csv_path = Path(os.path.expandvars(result_file_path)).expanduser()
    if not csv_path.is_absolute():
        csv_path = ENV_PATH.parent / csv_path

    return csv_path.resolve(strict=False)


@st.cache_data(show_spinner=False)
def load_uploaded_data(raw_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(raw_bytes))


@st.cache_data(show_spinner=False)
def load_csv_file(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required = {"context_tokens", "depth", "needle", "predicted"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Results CSV is missing required column(s): {sorted(missing)}")
        st.stop()

    if "context_tokens_binned" not in df.columns:
        df["context_tokens_binned"] = (
            (df["context_tokens"] / 1000).round().astype(int) * 1000
        )

    if "latency_sec" not in df.columns:
        df["latency_sec"] = np.nan

    classified = df.apply(
        lambda r: classify_row(r["needle"], r["predicted"]), axis=1, result_type="expand"
    )
    classified.columns = ["category", "lexical_match", "semantic_correct", "needle_code"]
    df = pd.concat([df, classified], axis=1)

    if "success" not in df.columns:
        df["success"] = df["lexical_match"]
    df["success"] = df["success"].astype(bool)

    df["depth_pct"] = (df["depth"] * 100).round(0).astype(int)
    df["reported_vs_recomputed_agree"] = df["success"] == df["lexical_match"]

    return df


# ----------------------------------------------------------------------------
# Sidebar - data source & filters
# ----------------------------------------------------------------------------
st.sidebar.title("🔎 NIAH Dashboard")
st.sidebar.caption("Long-range dependency / retrieval evaluation")

st.sidebar.subheader("Data")
uploaded_file = st.sidebar.file_uploader("Upload results CSV", type=["csv"])

if uploaded_file is not None:
    raw_df = load_uploaded_data(uploaded_file.getvalue())
    st.sidebar.success(f"Loaded {len(raw_df)} rows from upload.")
else:
    result_path = get_result_file_path()
    if not result_path.exists():
        st.error(f"RESULT_FILE_PATH points to a missing CSV: {result_path}")
        st.stop()
    raw_df = load_csv_file(str(result_path))
    st.sidebar.success(f"Loaded {len(raw_df)} rows from {result_path}.")

df_all = prepare_dataframe(raw_df)

st.sidebar.subheader("Filters")
needles = sorted(df_all["needle"].unique().tolist())
sel_needles = st.sidebar.multiselect("Needle prompt(s)", needles, default=needles)

ctx_values = sorted(df_all["context_tokens_binned"].unique().tolist())
sel_ctx = st.sidebar.multiselect(
    "Context length (tokens)", ctx_values, default=ctx_values, format_func=lambda x: f"{int(x):,}"
)

depth_values = sorted(df_all["depth_pct"].unique().tolist())
sel_depth = st.sidebar.multiselect(
    "Needle depth (%)", depth_values, default=depth_values, format_func=lambda x: f"{x}%"
)

df = df_all[
    df_all["needle"].isin(sel_needles)
    & df_all["context_tokens_binned"].isin(sel_ctx)
    & df_all["depth_pct"].isin(sel_depth)
].copy()

if df.empty:
    st.warning("No rows match the current filters.")
    st.stop()

# ----------------------------------------------------------------------------
# Header + methodology
# ----------------------------------------------------------------------------
st.title("Needle-in-a-Haystack Evaluation Dashboard")
st.caption(
    "Lexical exact-match vs. semantic/logical correctness across context length and needle depth."
)

with st.expander("ℹ️ How correctness is scored (methodology)", expanded=False):
    st.markdown(
        """
Each response is checked for the exact needle payload (e.g. `ALPHA-9921-X`) and bucketed into:

| Category | Meaning |
|---|---|
| **Exact / Clean Match** | Output is (essentially) just the code, nothing else. |
| **Correct (Verbose)** | The code appears and the model asserts it as the answer, wrapped in prose. |
| **Correct but Denied/Confused** | The code is present in the output, but the model's own reasoning rejects it ("this looks like a placeholder/glitch") — lexically present, logically wrong. |
| **Hallucinated / Wrong** | No trace of the code; the model answers from unrelated surrounding context instead. |

**Lexical match** = the first two rows above (code present at all).
**Semantic/logical correctness** = the model both found *and* endorsed the code as the answer — this excludes the "Denied/Confused" bucket, since technically-present-but-rejected is not a usable answer.

Your harness's own `success` column is also shown for comparison — in this data it matches the *lexical* definition (substring containment), which is why a response can be marked `True` even when several sentences of hedging surround the code.
        """
    )

# ----------------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------------
total = len(df)
lexical_acc = df["lexical_match"].mean()
semantic_acc = df["semantic_correct"].mean()
reported_acc = df["success"].mean()
confused_n = (df["category"] == "Correct but Denied/Confused").sum()
avg_latency = df["latency_sec"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Test cases", f"{total}")
c2.metric("Reported success (harness)", f"{reported_acc:.0%}")
c3.metric("Lexical match (recomputed)", f"{lexical_acc:.0%}")
c4.metric(
    "Semantic/logical correctness",
    f"{semantic_acc:.0%}",
    delta=f"{(semantic_acc - lexical_acc):.0%} vs lexical",
    delta_color="inverse",
)
c5.metric("Avg latency", f"{avg_latency:.2f}s" if pd.notna(avg_latency) else "n/a")

if confused_n:
    st.warning(
        f"{confused_n} response(s) contained the correct code but the model talked itself "
        f"out of it (denied/confused) — lexically 'successful' but not a reliable answer."
    )

st.divider()

# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_overview, tab_failures, tab_latency, tab_data, tab_ai = st.tabs(
    ["📊 Heatmaps & Trends", "🧩 Failure Analysis", "⏱️ Latency", "📋 Raw Data & Export", "🤖 AI Judge (optional)"]
)

# ---- Tab 1: Heatmaps & trends ----------------------------------------------
with tab_overview:
    st.subheader("Classic NIAH heatmap: context length × depth")
    metric_choice = st.radio(
        "Metric", ["Semantic/logical correctness", "Lexical match", "Reported success (harness)"],
        horizontal=True, key="heatmap_metric"
    )
    col_map = {
        "Semantic/logical correctness": "semantic_correct",
        "Lexical match": "lexical_match",
        "Reported success (harness)": "success",
    }
    value_col = col_map[metric_choice]

    pivot = (
        df.groupby(["depth_pct", "context_tokens_binned"])[value_col]
        .mean()
        .unstack("context_tokens_binned")
        .sort_index(ascending=False)
    )
    fig_heat = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[f"{int(c):,}" for c in pivot.columns],
            y=[f"{int(d)}%" for d in pivot.index],
            colorscale="RdYlGn",
            zmin=0,
            zmax=1,
            text=[[f"{v:.0%}" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            colorbar=dict(title="Accuracy", tickformat=".0%"),
        )
    )
    fig_heat.update_layout(
        xaxis_title="Context length (tokens)",
        yaxis_title="Needle depth",
        height=380,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig_heat, width="stretch")

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Accuracy vs. context length")
        trend = (
            df.groupby("context_tokens_binned")[["lexical_match", "semantic_correct"]]
            .mean()
            .reset_index()
            .sort_values("context_tokens_binned")
        )
        fig_trend = go.Figure()
        fig_trend.add_trace(
            go.Scatter(
                x=trend["context_tokens_binned"], y=trend["lexical_match"],
                mode="lines+markers", name="Lexical match",
            )
        )
        fig_trend.add_trace(
            go.Scatter(
                x=trend["context_tokens_binned"], y=trend["semantic_correct"],
                mode="lines+markers", name="Semantic/logical correct",
            )
        )
        fig_trend.update_layout(
            yaxis_tickformat=".0%", yaxis_range=[0, 1.05],
            xaxis_title="Context length (tokens)", yaxis_title="Accuracy",
            height=360, legend=dict(orientation="h", y=-0.25),
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_trend, width="stretch")

    with col_b:
        st.subheader("Accuracy vs. needle depth")
        trend_d = (
            df.groupby("depth_pct")[["lexical_match", "semantic_correct"]]
            .mean()
            .reset_index()
            .sort_values("depth_pct")
        )
        fig_depth = go.Figure()
        fig_depth.add_trace(
            go.Bar(x=trend_d["depth_pct"], y=trend_d["lexical_match"], name="Lexical match")
        )
        fig_depth.add_trace(
            go.Bar(x=trend_d["depth_pct"], y=trend_d["semantic_correct"], name="Semantic/logical correct")
        )
        fig_depth.update_layout(
            barmode="group", yaxis_tickformat=".0%", yaxis_range=[0, 1.05],
            xaxis_title="Needle depth (%)", yaxis_title="Accuracy",
            height=360, legend=dict(orientation="h", y=-0.25),
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_depth, width="stretch")

# ---- Tab 2: Failure analysis -----------------------------------------------
with tab_failures:
    st.subheader("Response category breakdown")
    cat_counts = (
        df["category"].value_counts().reindex(CATEGORY_ORDER).dropna().astype(int).reset_index()
    )
    cat_counts.columns = ["category", "count"]
    fig_cat = px.bar(
        cat_counts, x="count", y="category", orientation="h",
        color="category", color_discrete_map=CATEGORY_COLORS, text="count",
    )
    fig_cat.update_layout(
        showlegend=False, height=320, xaxis_title="# of responses", yaxis_title="",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_cat, width="stretch")

    st.subheader("Where does correctness break down?")
    stacked = (
        df.groupby(["context_tokens_binned", "category"]).size()
        .unstack(fill_value=0)
        .reindex(columns=CATEGORY_ORDER, fill_value=0)
    )
    fig_stack = go.Figure()
    for cat in CATEGORY_ORDER:
        if cat in stacked.columns:
            fig_stack.add_trace(
                go.Bar(
                    x=[f"{int(c):,}" for c in stacked.index], y=stacked[cat],
                    name=cat, marker_color=CATEGORY_COLORS[cat],
                )
            )
    fig_stack.update_layout(
        barmode="stack", xaxis_title="Context length (tokens)", yaxis_title="# of responses",
        height=360, legend=dict(orientation="h", y=-0.3),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_stack, width="stretch")

    st.subheader("Review individual failures")
    fail_df = df[df["category"] != "Exact / Clean Match"].reset_index(drop=True)
    if fail_df.empty:
        st.success("No failures in the current filter selection 🎉")
    else:
        idx = st.number_input(
            "Row to inspect", min_value=0, max_value=len(fail_df) - 1, value=0, step=1
        )
        row = fail_df.iloc[idx]
        badge_color = CATEGORY_COLORS.get(row["category"], "#999999")
        st.markdown(
            f"<span style='background-color:{badge_color}; color:black; padding:2px 10px; "
            f"border-radius:10px; font-size:0.85em'>{row['category']}</span>",
            unsafe_allow_html=True,
        )
        m1, m2, m3 = st.columns(3)
        m1.write(f"**Context:** {int(row['context_tokens']):,} tokens")
        m2.write(f"**Depth:** {row['depth_pct']}%")
        m3.write(f"**Latency:** {row['latency_sec']:.2f}s" if pd.notna(row["latency_sec"]) else "n/a")
        st.text_area("Needle (ground truth)", row["needle"], height=60, disabled=True)
        st.text_area("Model prediction", row["predicted"], height=180, disabled=True)

# ---- Tab 3: Latency ---------------------------------------------------------
with tab_latency:
    st.subheader("Latency vs. context length")
    fig_lat = px.scatter(
        df, x="context_tokens", y="latency_sec", color="category",
        color_discrete_map=CATEGORY_COLORS,
        hover_data=["depth_pct", "needle"],
        labels={"context_tokens": "Context length (tokens)", "latency_sec": "Latency (s)"},
    )
    fig_lat.update_layout(height=420, legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig_lat, width="stretch")

    st.subheader("Average latency by context bucket")
    lat_stats = (
        df.groupby("context_tokens_binned")["latency_sec"]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
    )
    fig_lat_bar = go.Figure(
        data=go.Bar(
            x=[f"{int(c):,}" for c in lat_stats["context_tokens_binned"]],
            y=lat_stats["mean"],
            error_y=dict(type="data", array=lat_stats["std"].fillna(0)),
        )
    )
    fig_lat_bar.update_layout(
        xaxis_title="Context length (tokens)", yaxis_title="Mean latency (s)", height=360,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_lat_bar, width="stretch")
    st.dataframe(lat_stats.style.format({"mean": "{:.2f}", "std": "{:.2f}", "min": "{:.2f}", "max": "{:.2f}"}), width="stretch")

# ---- Tab 4: Raw data & export ----------------------------------------------
with tab_data:
    st.subheader("Filtered results")
    search = st.text_input("Search within predictions", "")
    view_df = df.copy()
    if search:
        view_df = view_df[view_df["predicted"].str.contains(search, case=False, na=False)]

    display_cols = [
        "context_tokens", "depth_pct", "needle", "predicted", "success",
        "lexical_match", "semantic_correct", "category", "latency_sec",
    ]
    st.dataframe(view_df[display_cols], width="stretch", height=420)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download annotated results (CSV)",
        data=csv_bytes,
        file_name="niah_results_annotated.csv",
        mime="text/csv",
    )

# ---- Tab 5: Optional LLM-as-judge -------------------------------------------
with tab_ai:
    st.subheader("Optional: double-check ambiguous rows with Claude")
    st.caption(
        "The heuristic classifier above is regex-based and fast, but can't catch every "
        "edge case. You can optionally have Claude re-judge a subset of rows for a second opinion. "
        "This uses your own Anthropic API key and is entirely optional."
    )

    api_key = st.text_input("Anthropic API key", type="password", help="Not stored anywhere; used only for this session.")
    model = st.selectbox("Model", ["claude-sonnet-5", "claude-haiku-4-5-20251001", "claude-opus-4-8"], index=0)
    subset_choice = st.radio(
        "Which rows to judge?",
        ["Only 'Correct but Denied/Confused' + 'Hallucinated / Wrong'", "All filtered rows"],
        index=0,
    )
    max_rows = st.number_input("Max rows to send (cost control)", min_value=1, max_value=200, value=10)

    if subset_choice.startswith("Only"):
        candidates = df[df["category"].isin(["Correct but Denied/Confused", "Hallucinated / Wrong"])]
    else:
        candidates = df
    candidates = candidates.head(int(max_rows))

    st.write(f"{len(candidates)} row(s) queued for judging.")

    if st.button("Run AI judge", type="primary", disabled=not api_key):
        try:
            import anthropic
        except ImportError:
            st.error("The `anthropic` package isn't installed. Run: pip install anthropic")
            st.stop()

        client = anthropic.Anthropic(api_key=api_key)
        results = []
        progress = st.progress(0.0)
        for i, (_, row) in enumerate(candidates.iterrows()):
            prompt = textwrap.dedent(f"""
                A model was given a long document with a hidden "needle" fact and asked
                to find it. Judge whether the model's response correctly and confidently
                identifies the needle as the answer.

                Needle (ground truth): {row['needle']}
                Model's response: {row['predicted']}

                Reply with ONLY a JSON object, no other text:
                {{"semantically_correct": true or false, "reasoning": "one short sentence"}}
            """).strip()
            try:
                resp = client.messages.create(
                    model=model, max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text.strip()
                text = re.sub(r"^```json|```$", "", text).strip()
                parsed = json.loads(text)
                results.append({
                    "needle": row["needle"],
                    "predicted": row["predicted"][:120] + ("…" if len(row["predicted"]) > 120 else ""),
                    "heuristic_category": row["category"],
                    "ai_semantically_correct": parsed.get("semantically_correct"),
                    "ai_reasoning": parsed.get("reasoning"),
                })
            except Exception as e:
                results.append({
                    "needle": row["needle"],
                    "predicted": row["predicted"][:120],
                    "heuristic_category": row["category"],
                    "ai_semantically_correct": None,
                    "ai_reasoning": f"error: {e}",
                })
            progress.progress((i + 1) / len(candidates))

        result_df = pd.DataFrame(results)
        st.dataframe(result_df, width="stretch")
        agree = (
            (result_df["ai_semantically_correct"] == True) & result_df["heuristic_category"].isin(["Exact / Clean Match", "Correct (Verbose)"])
        ) | (
            (result_df["ai_semantically_correct"] == False) & result_df["heuristic_category"].isin(["Correct but Denied/Confused", "Hallucinated / Wrong"])
        )
        if len(result_df):
            st.metric("Agreement with heuristic classifier", f"{agree.mean():.0%}")
