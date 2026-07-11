"""Streamlit UI: side-by-side comparison of Claude vs. Cortex Analyst NL→SQL."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pandas as pd
import streamlit as st

from src.claude_runner import ClaudeRunner
from src.comparator import compare
from src.config import Config
from src.cortex_runner import CortexAnalystRunner
from src.forecast import (
    build_chart,
    discover_forecast_tables,
    discover_source_tables,
    list_columns,
    load_forecast,
    load_history,
)
from src.introspector import introspect
from src.logger import ensure_table, log_run
from src.semantic_loader import load as load_semantic_model
from src.semantic_loader import to_system_prompt, verified_queries
from src.snowflake_client import SnowflakeClient

st.set_page_config(page_title="NL→SQL: Claude vs. Cortex Analyst", layout="wide")

MODES = {
    "Compare: Claude vs. Cortex Analyst": "compare",
    "Claude only: semantic model": "claude_semantic",
    "Claude only: introspect schema": "claude_introspect",
}


@st.cache_resource
def bootstrap_base():
    """One-time setup shared by every mode: config, connection, run-log table."""
    cfg = Config.from_env()
    sf = SnowflakeClient(cfg)
    ensure_table(sf, cfg)
    return cfg, sf


def _load_curated_model(cfg, sf):
    """Semantic-model YAML: local file if configured, else download from the stage."""
    if cfg.semantic_model_local_path:
        return load_semantic_model(Path(cfg.semantic_model_local_path)), cfg.semantic_model_local_path
    if cfg.semantic_model_stage_path:
        yaml_path = sf.download_from_stage(cfg.semantic_model_stage_path)
        return load_semantic_model(yaml_path), cfg.semantic_model_stage_path
    raise RuntimeError(
        "No semantic model configured — set SEMANTIC_MODEL_STAGE_PATH or "
        "SEMANTIC_MODEL_LOCAL_PATH in .env, or switch to introspect mode."
    )


@st.cache_resource
def build_runners(mode: str):
    """Per-mode setup: schema context + runners. Cortex runner only in compare mode.

    - compare:            stage YAML is the single source of truth (Cortex needs it
                          on the stage, Claude gets the downloaded copy)
    - claude_semantic:    local YAML if set, else stage YAML; no Cortex
    - claude_introspect:  schema context built live from INFORMATION_SCHEMA; no Cortex
    """
    cfg, sf = bootstrap_base()

    if mode == "compare":
        if not cfg.semantic_model_stage_path:
            raise RuntimeError(
                "Compare mode needs SEMANTIC_MODEL_STAGE_PATH in .env — Cortex Analyst "
                "reads the semantic model from a Snowflake stage. Use a Claude-only "
                "mode if you don't have one."
            )
        yaml_path = sf.download_from_stage(cfg.semantic_model_stage_path)
        model = load_semantic_model(yaml_path)
        claude = ClaudeRunner(cfg.anthropic_api_key, to_system_prompt(model), sf)
        cortex = CortexAnalystRunner(cfg, sf, cfg.semantic_model_stage_path)
        return model, claude, cortex, cfg.semantic_model_stage_path

    if mode == "claude_semantic":
        model, source = _load_curated_model(cfg, sf)
        claude = ClaudeRunner(cfg.anthropic_api_key, to_system_prompt(model), sf)
        return model, claude, None, source

    # claude_introspect
    model = introspect(sf, cfg.sf_database, cfg.sf_schema)
    system_prompt = to_system_prompt(model, physical_schema=True)
    claude = ClaudeRunner(cfg.anthropic_api_key, system_prompt, sf)
    return model, claude, None, f"INFORMATION_SCHEMA of {cfg.sf_database}.{cfg.sf_schema}"


@st.cache_data(ttl=300, show_spinner=False)
def _cached_forecast_tables(_sf: SnowflakeClient, db: str, schema: str) -> list[str]:
    return discover_forecast_tables(_sf, _sf.cfg)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_source_tables(
    _sf: SnowflakeClient, db: str, schema: str, exclude: tuple[str, ...]
) -> list[str]:
    return discover_source_tables(_sf, _sf.cfg, exclude=list(exclude))


@st.cache_data(ttl=300, show_spinner=False)
def _cached_columns(_sf: SnowflakeClient, table: str) -> list[tuple[str, str]]:
    return list_columns(_sf, _sf.cfg, table)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_load_forecast(_sf: SnowflakeClient, table: str):
    return load_forecast(_sf, table)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_load_history(
    _sf: SnowflakeClient, source_table: str, ts_col: str, value_col: str, end_ts_iso: str
) -> pd.DataFrame:
    end_ts = pd.Timestamp(end_ts_iso) if end_ts_iso else None
    return load_history(_sf, source_table, ts_col, value_col, end_ts=end_ts)


def _run_claude_only(claude, question: str):
    if not st.button("Ask Claude", type="primary"):
        return

    with st.spinner("Asking Claude..."):
        result = claude.ask(question)

    m1, m2, m3 = st.columns(3)
    m1.metric("Latency", f"{result.elapsed_ms} ms")
    m2.metric("Turns", result.turns)
    m3.metric(
        "Tokens",
        f"{result.input_tokens + result.output_tokens}",
        f"cache read: {result.cache_read_tokens}",
    )

    st.divider()
    st.subheader("🤖 Claude (Sonnet 4.6)")
    if result.error:
        st.error(result.error)
        return
    if result.final_sql:
        st.code(result.final_sql, language="sql")
    else:
        st.warning("Claude did not produce a final SQL statement.")
    if result.final_result is not None and not result.final_result.rows.empty:
        st.dataframe(result.final_result.rows, use_container_width=True)
    if result.explanation:
        st.markdown(f"**Explanation:** {result.explanation}")

    with st.expander("Claude conversation history"):
        st.json(result.history, expanded=False)


def _render_compare_tab(cfg, sf, model, claude, cortex):
    def _set_question(q: str) -> None:
        st.session_state.question = q

    question = st.text_input(
        "Ask a question about your data",
        placeholder="Type your question or pick a verified one below",
        key="question",
    )

    if not question:
        vqs = verified_queries(model)
        if vqs:
            st.write("**Verified queries from your semantic model:**")
            st.caption("Click any to load it into the input above.")
            for i, q in enumerate(vqs):
                st.button(
                    q["question"],
                    key=f"vq_{i}",
                    use_container_width=True,
                    on_click=_set_question,
                    args=(q["question"],),
                )
        else:
            st.info(
                "Type a question about your data to get started. "
                "Add a `verified_queries` block to your semantic model to populate this list."
            )
        return

    if cortex is None:
        _run_claude_only(claude, question)
        return

    if not st.button("Run comparison", type="primary"):
        return

    with st.spinner("Asking Claude and Cortex Analyst in parallel..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            claude_future = pool.submit(claude.ask, question)
            cortex_future = pool.submit(cortex.ask, question)
            claude_result = claude_future.result()
            cortex_result = cortex_future.result()

    comparison = compare(claude_result, cortex_result)

    v1, v2, v3, v4 = st.columns(4)
    v1.metric(
        "Rows match",
        "✓" if comparison.rows_match else "✗",
        comparison.detail if not comparison.rows_match else "identical row sets",
    )
    v2.metric("Claude latency", f"{claude_result.elapsed_ms} ms")
    v3.metric("Cortex Analyst latency", f"{cortex_result.elapsed_ms} ms")
    v4.metric(
        "Claude tokens",
        f"{claude_result.input_tokens + claude_result.output_tokens}",
        f"cache read: {claude_result.cache_read_tokens}",
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("🤖 Claude (Sonnet 4.6)")
        if claude_result.error:
            st.error(claude_result.error)
        else:
            st.caption(f"Resolved in {claude_result.turns} turns")
            if claude_result.final_sql:
                st.code(claude_result.final_sql, language="sql")
            else:
                st.warning("Claude did not produce a final SQL statement.")
            if claude_result.final_result is not None and not claude_result.final_result.rows.empty:
                st.dataframe(claude_result.final_result.rows, use_container_width=True)
            if claude_result.explanation:
                st.markdown(f"**Explanation:** {claude_result.explanation}")

    with right:
        st.subheader("❄️ Cortex Analyst")
        if cortex_result.error:
            st.error(cortex_result.error)
        if cortex_result.final_sql:
            st.code(cortex_result.final_sql, language="sql")
        else:
            st.warning("Cortex Analyst did not return a SQL statement.")
        if cortex_result.final_result is not None and not cortex_result.final_result.rows.empty:
            st.dataframe(cortex_result.final_result.rows, use_container_width=True)
        if cortex_result.explanation:
            st.markdown(f"**Explanation:** {cortex_result.explanation}")
        if cortex_result.request_id:
            st.caption(f"x-snowflake-request-id: `{cortex_result.request_id}`")

    st.divider()

    st.subheader("Which did better?")
    f1, f2, f3, f4 = st.columns(4)
    feedback = None
    if f1.button("👍 Claude"):
        feedback = "claude_better"
    if f2.button("👍 Cortex"):
        feedback = "cortex_better"
    if f3.button("🤝 Tie"):
        feedback = "tie"
    if f4.button("⏭ Skip logging"):
        feedback = "skipped"

    if feedback is not None and feedback != "skipped":
        try:
            log_run(sf, cfg, question, claude_result, cortex_result, comparison, feedback)
            st.success(f"Logged to {cfg.run_log_table} with feedback: {feedback}")
        except Exception as e:
            st.error(f"Failed to log run: {e}")

    with st.expander("Raw Cortex Analyst response"):
        st.json(cortex_result.raw_response)
    with st.expander("Claude conversation history"):
        st.json(claude_result.history, expanded=False)


def _render_forecast_tab(cfg, sf):
    st.subheader("Snowflake forecast viewer")
    st.caption(
        f"Discovers tables matching `%FORECAST%` in `{cfg.sf_database}.{cfg.sf_schema}` "
        "and renders the point forecast with its confidence band."
    )

    forecast_tables = _cached_forecast_tables(sf, cfg.sf_database, cfg.sf_schema)
    if not forecast_tables:
        st.info(
            f"No forecast tables found in `{cfg.sf_database}.{cfg.sf_schema}`. "
            "Forecast discovery looks for table names containing `FORECAST`."
        )
        return

    selected = st.selectbox("Forecast table", forecast_tables, key="fc_table")

    try:
        series = _cached_load_forecast(sf, selected)
    except Exception as e:
        st.error(f"Could not load forecast from {selected}: {e}")
        return

    fc_df = series.df
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forecast points", f"{len(fc_df):,}")
    m2.metric("Start", fc_df["ts"].min().strftime("%Y-%m-%d"))
    m3.metric("End", fc_df["ts"].max().strftime("%Y-%m-%d"))
    horizon_days = (fc_df["ts"].max() - fc_df["ts"].min()).days
    m4.metric("Horizon", f"{horizon_days} days")

    history_df: pd.DataFrame | None = None
    value_label = "Forecast value"

    with st.expander("History overlay (optional)", expanded=True):
        overlay = st.checkbox(
            "Overlay actuals from a source table", value=True, key="fc_overlay"
        )
        if overlay:
            source_tables = _cached_source_tables(
                sf, cfg.sf_database, cfg.sf_schema, tuple(forecast_tables)
            )
            if not source_tables:
                st.info("No non-forecast base tables found in this schema.")
            else:
                src = st.selectbox("Source table", source_tables, key="fc_source")
                cols = _cached_columns(sf, src)
                if not cols:
                    st.warning(f"No columns found for {src}.")
                else:
                    ts_candidates = [
                        c for c, t in cols
                        if "DATE" in t.upper() or "TIMESTAMP" in t.upper()
                    ]
                    num_candidates = [
                        c for c, t in cols
                        if any(k in t.upper() for k in ("NUMBER", "FLOAT", "INT", "DECIMAL"))
                    ]
                    all_cols = [c for c, _ in cols]

                    c1, c2 = st.columns(2)
                    ts_col = c1.selectbox(
                        "Timestamp column",
                        ts_candidates or all_cols,
                        key="fc_ts_col",
                    )
                    value_col = c2.selectbox(
                        "Value column",
                        num_candidates or all_cols,
                        key="fc_value_col",
                    )
                    value_label = value_col
                    try:
                        history_df = _cached_load_history(
                            sf,
                            src,
                            ts_col,
                            value_col,
                            end_ts_iso=fc_df["ts"].max().isoformat(),
                        )
                        if history_df.empty:
                            st.warning(
                                f"No history rows returned from {src} "
                                f"(checked {ts_col} ≤ {fc_df['ts'].max().date()})."
                            )
                            history_df = None
                    except Exception as e:
                        st.error(f"Could not load history: {e}")
                        history_df = None

    fig = build_chart(series, history=history_df, value_label=value_label)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Forecast rows"):
        st.dataframe(fc_df, use_container_width=True)


def main():
    st.title("Natural Language → Snowflake SQL")

    with st.sidebar:
        st.subheader("Mode")
        mode_label = st.radio(
            "Mode",
            list(MODES),
            key="mode",
            label_visibility="collapsed",
            help=(
                "Compare needs a semantic-model YAML on a Snowflake stage. "
                "Introspect builds schema context live from INFORMATION_SCHEMA — "
                "no YAML required."
            ),
        )
    mode = MODES[mode_label]

    if mode == "compare":
        st.caption("Claude (with your semantic model) vs. Snowflake Cortex Analyst — side by side")
    elif mode == "claude_semantic":
        st.caption("Claude with your semantic-model YAML — no Cortex Analyst call")
    else:
        st.caption("Claude with schema context introspected from INFORMATION_SCHEMA — zero YAML setup")

    try:
        cfg, sf = bootstrap_base()
        model, claude, cortex, source = build_runners(mode)
    except Exception as e:
        st.error(f"Bootstrap failed: {e}")
        st.info("Check your `.env` against `.env.example` and verify Snowflake credentials.")
        return

    with st.sidebar:
        st.divider()
        st.subheader("Schema context")
        st.write(f"**{model.name}**")
        if model.description:
            st.caption(model.description)
        st.caption(f"Source: `{source}`")
        with st.expander("View YAML"):
            st.code(model.raw_yaml, language="yaml")
        st.divider()
        st.subheader("Connection")
        st.text(f"Account:  {cfg.sf_account}")
        st.text(f"Database: {cfg.sf_database}")
        st.text(f"Schema:   {cfg.sf_schema}")

    tab_label = "Compare NL→SQL" if cortex is not None else "Ask NL→SQL"
    compare_tab, forecast_tab = st.tabs([tab_label, "📈 Forecasting"])

    with compare_tab:
        _render_compare_tab(cfg, sf, model, claude, cortex)

    with forecast_tab:
        _render_forecast_tab(cfg, sf)


if __name__ == "__main__":
    main()
