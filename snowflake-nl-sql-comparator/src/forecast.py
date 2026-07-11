"""Forecasting tab helpers: discover forecast tables, load series, render charts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from .config import Config
from .snowflake_client import SnowflakeClient

# Canonical column names produced by SNOWFLAKE.ML.FORECAST.
TS_COL = "TS"
FORECAST_COL = "FORECAST"
LOWER_COL = "LOWER_BOUND"
UPPER_COL = "UPPER_BOUND"
REQUIRED_FORECAST_COLS = (TS_COL, FORECAST_COL, LOWER_COL, UPPER_COL)


@dataclass(frozen=True)
class ForecastSeries:
    table: str
    df: pd.DataFrame  # columns: ts, forecast, lower_bound, upper_bound (lowercased)


def discover_forecast_tables(sf: SnowflakeClient, cfg: Config) -> list[str]:
    """Return fully-qualified forecast table names in the configured schema.

    Heuristic: any BASE TABLE / VIEW whose name contains 'FORECAST'.
    """
    sql = f"""
        SELECT TABLE_NAME
        FROM {cfg.sf_database}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = '{cfg.sf_schema.upper()}'
          AND TABLE_NAME ILIKE '%FORECAST%'
        ORDER BY TABLE_NAME
    """
    result = sf.execute(sql)
    if result.error or result.rows.empty:
        return []
    return [f"{cfg.sf_database}.{cfg.sf_schema}.{name}" for name in result.rows.iloc[:, 0]]


def discover_source_tables(
    sf: SnowflakeClient, cfg: Config, exclude: list[str] | None = None
) -> list[str]:
    """Return fully-qualified base tables in the configured schema, excluding forecast tables."""
    sql = f"""
        SELECT TABLE_NAME
        FROM {cfg.sf_database}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = '{cfg.sf_schema.upper()}'
          AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME NOT ILIKE '%FORECAST%'
        ORDER BY TABLE_NAME
    """
    result = sf.execute(sql)
    if result.error or result.rows.empty:
        return []
    excluded = {e.upper() for e in (exclude or [])}
    return [
        f"{cfg.sf_database}.{cfg.sf_schema}.{name}"
        for name in result.rows.iloc[:, 0]
        if f"{cfg.sf_database}.{cfg.sf_schema}.{name}".upper() not in excluded
    ]


def list_columns(sf: SnowflakeClient, cfg: Config, table: str) -> list[tuple[str, str]]:
    """Return [(column_name, data_type), ...] for a fully-qualified table."""
    # Split DB.SCHEMA.TABLE
    parts = table.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected DB.SCHEMA.TABLE, got: {table}")
    db, schema, tbl = parts
    sql = f"""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM {db}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{schema.upper()}'
          AND TABLE_NAME = '{tbl.upper()}'
        ORDER BY ORDINAL_POSITION
    """
    result = sf.execute(sql)
    if result.error or result.rows.empty:
        return []
    return [(row[0], row[1]) for row in result.rows.itertuples(index=False)]


def load_forecast(sf: SnowflakeClient, table: str) -> ForecastSeries:
    """Load TS, FORECAST, LOWER_BOUND, UPPER_BOUND from a forecast table.

    Column lookup is case-insensitive. Raises if any required column is missing.
    """
    result = sf.execute(f"SELECT * FROM {table} ORDER BY 1", row_limit=10_000)
    if result.error:
        raise RuntimeError(f"Failed to query {table}: {result.error}")

    df = result.rows
    upper_map = {c.upper(): c for c in df.columns}
    missing = [c for c in REQUIRED_FORECAST_COLS if c not in upper_map]
    if missing:
        raise ValueError(
            f"{table} is missing required column(s) {missing}. "
            f"Expected {list(REQUIRED_FORECAST_COLS)}, found {list(df.columns)}."
        )

    out = df[[upper_map[c] for c in REQUIRED_FORECAST_COLS]].copy()
    out.columns = ["ts", "forecast", "lower_bound", "upper_bound"]
    out["ts"] = pd.to_datetime(out["ts"])
    return ForecastSeries(table=table, df=out.sort_values("ts").reset_index(drop=True))


def load_history(
    sf: SnowflakeClient,
    source_table: str,
    ts_col: str,
    value_col: str,
    end_ts: pd.Timestamp | None = None,
    row_limit: int = 10_000,
) -> pd.DataFrame:
    """Load (ts, value) from a source table, optionally truncated at end_ts.

    Aggregates by ts (SUM) so multi-row-per-timestamp source tables collapse to one
    series before plotting.
    """
    where = ""
    if end_ts is not None:
        where = f"WHERE {ts_col} <= '{end_ts.isoformat()}'"
    sql = f"""
        SELECT {ts_col} AS ts, SUM({value_col}) AS value
        FROM {source_table}
        {where}
        GROUP BY {ts_col}
        ORDER BY ts
    """
    result = sf.execute(sql, row_limit=row_limit)
    if result.error:
        raise RuntimeError(f"Failed to query history from {source_table}: {result.error}")
    df = result.rows.copy()
    if df.empty:
        return df
    df.columns = ["ts", "value"]
    df["ts"] = pd.to_datetime(df["ts"])
    return df.sort_values("ts").reset_index(drop=True)


def build_chart(
    forecast: ForecastSeries,
    history: pd.DataFrame | None = None,
    value_label: str = "Value",
) -> go.Figure:
    """Build a Plotly figure: history + forecast line + shaded confidence band."""
    fig = go.Figure()
    fc = forecast.df
    forecast_start = fc["ts"].min()

    if history is not None and not history.empty:
        fig.add_trace(
            go.Scatter(
                x=history["ts"],
                y=history["value"],
                mode="lines",
                name="History",
                line=dict(color="rgb(31,119,180)", width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>Actual: %{y:,.2f}<extra></extra>",
            )
        )

    # Confidence band: upper (invisible line) + lower with fill back to upper.
    fig.add_trace(
        go.Scatter(
            x=fc["ts"],
            y=fc["upper_bound"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=fc["ts"],
            y=fc["lower_bound"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(255,127,14,0.2)",
            name="Confidence band",
            hovertemplate="%{x|%Y-%m-%d}<br>Lower: %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=fc["ts"],
            y=fc["forecast"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="rgb(255,127,14)", width=2),
            marker=dict(size=5),
            hovertemplate="%{x|%Y-%m-%d}<br>Forecast: %{y:,.2f}<extra></extra>",
        )
    )

    fig.add_vline(
        x=forecast_start,
        line_dash="dash",
        line_color="gray",
        annotation_text="Forecast start",
        annotation_position="top left",
    )

    fig.update_layout(
        title=f"Forecast: {forecast.table.split('.')[-1]}",
        xaxis_title="Date",
        yaxis_title=value_label,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=480,
    )
    return fig
