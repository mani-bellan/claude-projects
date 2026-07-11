"""Top-ranked stocks and SIPs for a long-term first-time investor."""

from __future__ import annotations

import sys
from pathlib import Path

_DASHBOARD = Path(__file__).resolve().parents[1]
if str(_DASHBOARD) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD))

import streamlit as st

from components import cards, charts, data, styling

st.set_page_config(page_title="Recommendations", page_icon="🏆", layout="wide")
styling.apply()

st.markdown("# Recommendations")
st.markdown("Ranked by composite long-term score. Filter by risk tolerance.")
styling.disclaimer()
styling.methodology()

# ---- Sidebar filters ------------------------------------------------------

with st.sidebar:
    st.markdown("### Filters")
    risk_choice = st.multiselect(
        "Risk tier",
        options=["LOW", "MEDIUM", "HIGH"],
        default=["LOW", "MEDIUM"],
    )
    min_score = st.slider("Minimum score", 0, 100, 0)

# ---- Stocks ---------------------------------------------------------------

st.markdown("## 📈 Top stocks")
stocks = data.stock_recommendations()
if stocks.is_empty():
    st.info("No stock recommendations yet. Run `make backfill` then `make features`.")
else:
    f = stocks.filter(
        stocks["risk_tier"].is_in(risk_choice) & (stocks["score"] >= min_score)
    )
    if f.is_empty():
        st.warning("No stocks match the current filters.")
    else:
        top3 = f.head(3).to_dicts()
        cols = st.columns(min(3, len(top3)))
        for col, row in zip(cols, top3):
            with col:
                cards.stock_top_card(row)
                st.plotly_chart(
                    charts.pillar_radar(row),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

        with st.expander(f"Full ranked list ({f.height})", expanded=False):
            display = f.select(
                [
                    "rank",
                    "ticker",
                    "score",
                    "risk_tier",
                    "primary_cagr",
                    "volatility",
                    "max_drawdown",
                    "years_history",
                    "rationale",
                ]
            ).rename(
                {
                    "primary_cagr": "CAGR",
                    "volatility": "Vol",
                    "max_drawdown": "MaxDD",
                    "years_history": "Years",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# ---- Mutual funds ---------------------------------------------------------

st.markdown("## 💰 Top SIPs")
mfs = data.mf_recommendations()
if mfs.is_empty():
    st.info("No SIP recommendations yet. Run `make backfill` then `make features`.")
else:
    f = mfs.filter(
        mfs["risk_tier"].is_in(risk_choice) & (mfs["score"] >= min_score)
    )
    if f.is_empty():
        st.warning("No SIPs match the current filters.")
    else:
        top3 = f.head(3).to_dicts()
        cols = st.columns(min(3, len(top3)))
        for col, row in zip(cols, top3):
            with col:
                cards.mf_top_card(row)
                st.plotly_chart(
                    charts.pillar_radar(row),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

        with st.expander(f"Full ranked list ({f.height})", expanded=False):
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
                    "years_history",
                ]
            ).rename(
                {
                    "scheme_name": "Scheme",
                    "scheme_category": "Category",
                    "is_elss": "ELSS",
                    "primary_cagr": "CAGR",
                    "volatility": "Vol",
                    "max_drawdown": "MaxDD",
                    "years_history": "Years",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)
