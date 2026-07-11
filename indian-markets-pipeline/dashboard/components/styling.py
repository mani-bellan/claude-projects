"""Inject CSS + Plotly theme. Call `apply()` at the top of every page."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


_CSS_PATH = Path(__file__).resolve().parent.parent / "theme" / "style.css"


def _inject_css() -> None:
    css = _CSS_PATH.read_text() if _CSS_PATH.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _register_plotly_theme() -> None:
    template = go.layout.Template(
        layout={
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#E0E6ED", "family": "Inter, system-ui, sans-serif"},
            "xaxis": {
                "gridcolor": "rgba(255,255,255,0.04)",
                "zerolinecolor": "rgba(255,255,255,0.1)",
                "linecolor": "rgba(255,255,255,0.1)",
            },
            "yaxis": {
                "gridcolor": "rgba(255,255,255,0.04)",
                "zerolinecolor": "rgba(255,255,255,0.1)",
                "linecolor": "rgba(255,255,255,0.1)",
            },
            "polar": {
                "bgcolor": "rgba(0,0,0,0)",
                "radialaxis": {
                    "gridcolor": "rgba(255,255,255,0.08)",
                    "linecolor": "rgba(255,255,255,0.1)",
                    "tickfont": {"size": 10, "color": "rgba(224,230,237,0.6)"},
                },
                "angularaxis": {
                    "gridcolor": "rgba(255,255,255,0.08)",
                    "linecolor": "rgba(255,255,255,0.1)",
                    "tickfont": {"size": 11, "color": "#E0E6ED"},
                },
            },
            "colorway": ["#00D9FF", "#FF00FF", "#FFD700", "#00FF88", "#FF6B6B", "#9B5FFF"],
            "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
        }
    )
    pio.templates["futuristic"] = template
    pio.templates.default = "futuristic"


_APPLIED_KEY = "_styling_applied"


def apply() -> None:
    """Idempotent: safe to call from every page."""
    if not st.session_state.get(_APPLIED_KEY):
        _register_plotly_theme()
        st.session_state[_APPLIED_KEY] = True
    _inject_css()


def disclaimer() -> None:
    st.markdown(
        '<div class="disclaimer">⚠️  Educational tool. Not financial advice. '
        "Past performance does not guarantee future returns. Consult a SEBI-registered "
        "advisor before investing.</div>",
        unsafe_allow_html=True,
    )


def methodology() -> None:
    """Plain-English explainer of how scores and ranks are built."""
    with st.expander("ℹ️  How are these ranked?", expanded=False):
        st.markdown(
            """
Every stock and SIP gets a **score out of 100**, built from four pillars
weighted to match what matters for a long-term, first-time investor:

| Pillar | Weight | What it measures | Why it matters |
|---|---|---|---|
| **Returns** | 40% | Annualised growth rate (CAGR), preferring 5-year, then 3-year, then 1-year | Tells you how fast wealth has compounded historically |
| **Stability** | 30% | Inverse of price volatility (lower swings → higher score) | A steadier ride is easier to hold through bad years |
| **Drawdown** | 20% | The worst peak-to-trough fall ever recorded | Caps the *bad-night* scenario — a smaller worst-case is safer |
| **Longevity** | 10% | Years of price / NAV history available | A 20-year track record carries more weight than a 2-year one |

**How the score is computed**

1. For each pillar, every instrument is **ranked against the rest of its universe** (Nifty 500 stocks, or the 30 curated SIPs) and assigned a percentile from 0 to 100.
2. The four pillar percentiles are blended using the weights above to produce the final 0–100 score.
3. The **risk tier** (LOW / MEDIUM / HIGH) is derived from the stability pillar alone — so a high-flying stock with great returns can still be tagged HIGH risk.
4. **Rank** is simply the descending order of score within the universe.

**How to read it**

- A score of **80+** means the instrument is in the top quintile of its universe across the weighted pillars.
- The **rationale** line ("Returns strong, stability average…") summarises which pillars are pulling weight.
- Same methodology runs daily — yesterday's #1 may shift as new data lands.

⚠️ This is a screening tool, not a buy/sell signal. Past performance does not guarantee future returns.
"""
        )


def tier_badge(tier: str) -> str:
    """HTML for an inline risk-tier pill — caller embeds with unsafe_allow_html."""
    return f'<span class="tier tier-{tier}">{tier}</span>'


def rank_badge(rank: int) -> str:
    return f'<div class="rank-badge">{rank}</div>'
