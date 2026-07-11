"""Filter and rank SIPs by category, ELSS, risk tier."""

from __future__ import annotations

import sys
from pathlib import Path

_DASHBOARD = Path(__file__).resolve().parents[1]
if str(_DASHBOARD) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD))

import polars as pl
import streamlit as st

from components import charts, data, styling

st.set_page_config(page_title="SIP Recommender", page_icon="💰", layout="wide")
styling.apply()

st.markdown("# SIP Recommender")
styling.disclaimer()
styling.methodology()

mfs = data.mf_recommendations()
if mfs.is_empty():
    st.info("No SIP recommendations yet.")
    st.stop()

with st.sidebar:
    st.markdown("### Filters")
    categories = sorted(c for c in mfs["scheme_category"].unique().to_list() if c)
    cat_choice = st.multiselect("Category", options=categories, default=categories)
    risk_choice = st.multiselect(
        "Risk tier", options=["LOW", "MEDIUM", "HIGH"], default=["LOW", "MEDIUM"]
    )
    elss_only = st.checkbox("ELSS (tax-saving) only", value=False)

f = mfs.filter(
    mfs["scheme_category"].is_in(cat_choice) & mfs["risk_tier"].is_in(risk_choice)
)
if elss_only:
    f = f.filter(pl.col("is_elss"))

if f.is_empty():
    st.warning("No SIPs match the current filters.")
    st.stop()

st.markdown(f"### {f.height} matching schemes")

display = f.select(
    [
        "rank",
        "scheme_name",
        "scheme_category",
        "is_elss",
        "score",
        "risk_tier",
        "primary_cagr",
        "volatility",
        "max_drawdown",
        "fund_house",
    ]
)
st.dataframe(display, use_container_width=True, hide_index=True)

# ---- NAV chart for selected scheme ---------------------------------------

st.markdown("### Inspect a scheme")
choice = st.selectbox(
    "Scheme",
    options=f["scheme_code"].to_list(),
    format_func=lambda code: (
        f.filter(pl.col("scheme_code") == code)["scheme_name"][0]
    ),
)

navs = data.mf_navs(choice)
if not navs.is_empty():
    st.plotly_chart(
        charts.price_chart(navs, value_col="nav"),
        use_container_width=True,
        config={"displayModeBar": False},
    )
