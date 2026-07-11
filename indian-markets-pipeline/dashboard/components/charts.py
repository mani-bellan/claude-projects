"""Reusable Plotly chart factories for the dashboard."""

from __future__ import annotations

import plotly.graph_objects as go
import polars as pl


def pillar_radar(row: dict, title: str | None = None) -> go.Figure:
    pillars = ["Returns", "Stability", "Drawdown", "Longevity"]
    keys = [
        "pillar_returns",
        "pillar_stability",
        "pillar_drawdown",
        "pillar_longevity",
    ]
    values = [float(row.get(k) or 0) for k in keys]
    fig = go.Figure(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=pillars + [pillars[0]],
            fill="toself",
            line=dict(color="#00D9FF", width=2),
            fillcolor="rgba(0, 217, 255, 0.18)",
            hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 100], showticklabels=False)),
        showlegend=False,
        height=260,
        margin=dict(l=20, r=20, t=20, b=20),
        title=title,
    )
    return fig


def price_chart(prices: pl.DataFrame, value_col: str = "adj_close") -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=prices["date"].to_list(),
            y=prices[value_col].to_list(),
            mode="lines",
            line=dict(color="#00D9FF", width=2),
            fill="tozeroy",
            fillcolor="rgba(0, 217, 255, 0.06)",
            hovertemplate="%{x|%b %d, %Y}<br>%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=320,
        showlegend=False,
        xaxis_title=None,
        yaxis_title=None,
    )
    return fig


def drawdown_chart(prices: pl.DataFrame, value_col: str = "adj_close") -> go.Figure:
    if prices.is_empty():
        return go.Figure()
    df = prices.with_columns(
        pl.col(value_col).cum_max().alias("peak")
    ).with_columns(
        ((pl.col(value_col) - pl.col("peak")) / pl.col("peak") * 100.0).alias("dd_pct")
    )
    fig = go.Figure(
        go.Scatter(
            x=df["date"].to_list(),
            y=df["dd_pct"].to_list(),
            mode="lines",
            line=dict(color="#FF6B6B", width=2),
            fill="tozeroy",
            fillcolor="rgba(255, 107, 107, 0.15)",
            hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f}%%<extra></extra>",
        )
    )
    fig.update_layout(
        height=240,
        showlegend=False,
        yaxis=dict(ticksuffix="%"),
    )
    return fig


def wealth_chart(timeline: pl.DataFrame) -> go.Figure:
    """timeline columns: date, invested, value."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=timeline["date"].to_list(),
            y=timeline["invested"].to_list(),
            mode="lines",
            name="Invested",
            line=dict(color="rgba(255, 255, 255, 0.4)", width=2, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=timeline["date"].to_list(),
            y=timeline["value"].to_list(),
            mode="lines",
            name="Portfolio value",
            line=dict(color="#00FF88", width=3),
            fill="tonexty",
            fillcolor="rgba(0, 255, 136, 0.10)",
        )
    )
    fig.update_layout(
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis=dict(tickprefix="₹", tickformat=",.0f"),
    )
    return fig
