"""Home — overview, freshness, navigation."""

from __future__ import annotations

import sys
from pathlib import Path

_DASHBOARD = Path(__file__).resolve().parent
if str(_DASHBOARD) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD))

import streamlit as st

from components import data, styling

st.set_page_config(
    page_title="Indian Markets · Long-term picks",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
styling.apply()

st.markdown("# Indian Markets")
st.markdown(
    "##### Long-term picks for first-time investors — built on 20 years of NSE & AMFI data"
)
styling.disclaimer()

# ---- Freshness panel ------------------------------------------------------

try:
    fresh = data.freshness()
    counts = data.row_counts()

    cols = st.columns(4)
    cols[0].metric(
        "Latest stock data",
        str(fresh["stock_prices"]) if fresh["stock_prices"] else "—",
        f"{counts['stock_prices']:,} rows",
    )
    cols[1].metric(
        "Latest NAV data",
        str(fresh["mf_navs"]) if fresh["mf_navs"] else "—",
        f"{counts['mf_navs']:,} rows",
    )
    cols[2].metric(
        "Stock recs",
        f"{counts['stock_recommendations']}" if counts["stock_recommendations"] else "—",
        "ranked & scored",
    )
    cols[3].metric(
        "SIP recs",
        f"{counts['mf_recommendations']}" if counts["mf_recommendations"] else "—",
        "ranked & scored",
    )
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

st.markdown("---")

# ---- Methodology ----------------------------------------------------------

left, right = st.columns([2, 1])
with left:
    st.markdown("### How picks are scored")
    st.markdown(
        """
Each instrument is ranked on four pillars, normalized within its universe:

- **Returns (40%)** — best-available CAGR (5y → 3y → 1y fallback)
- **Stability (30%)** — inverse annualized volatility
- **Drawdown (20%)** — worst peak-to-trough decline (less negative = better)
- **Longevity (10%)** — years of price/NAV history

A LOW risk tier means the instrument sits in the top third of its universe by stability.
"""
    )
with right:
    st.markdown("### Pages")
    st.page_link("pages/1_Recommendations.py", label="🏆 Recommendations", icon=None)
    st.page_link("pages/2_Stock_Explorer.py", label="📈 Stock Explorer", icon=None)
    st.page_link("pages/3_SIP_Recommender.py", label="💰 SIP Recommender", icon=None)
    st.page_link("pages/4_Portfolio_Simulator.py", label="🧪 Portfolio Simulator", icon=None)
