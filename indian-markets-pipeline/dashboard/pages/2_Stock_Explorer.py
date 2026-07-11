"""Pick a ticker, see price, drawdown, and pillar profile."""

from __future__ import annotations

import sys
from pathlib import Path

_DASHBOARD = Path(__file__).resolve().parents[1]
if str(_DASHBOARD) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD))

import streamlit as st

from components import charts, data, styling

st.set_page_config(page_title="Stock Explorer", page_icon="📈", layout="wide")
styling.apply()

st.markdown("# Stock Explorer")
styling.disclaimer()
styling.methodology()

stocks = data.stock_recommendations()
if stocks.is_empty():
    st.info("No stock data yet. Run the pipeline first.")
    st.stop()

with st.sidebar:
    st.markdown("### Choose a stock")
    tickers = stocks.sort("rank")["ticker"].to_list()
    ticker = st.selectbox("Ticker", options=tickers)

row = stocks.filter(stocks["ticker"] == ticker).to_dicts()[0]

# ---- KPI strip ------------------------------------------------------------

cols = st.columns(5)
cols[0].metric("Rank", f"#{int(row['rank'])}")
cols[1].metric("Score", f"{row['score']:.0f}/100")
cols[2].metric("Risk", row["risk_tier"])
cagr = row.get("primary_cagr")
cols[3].metric("CAGR", f"{cagr * 100:+.1f}%/yr" if cagr is not None else "—")
cols[4].metric("Volatility", f"{(row.get('volatility') or 0) * 100:.1f}%")

st.markdown(f"_{row.get('rationale') or ''}_")

# ---- Price + drawdown -----------------------------------------------------

prices = data.stock_prices(ticker)
if prices.is_empty():
    st.warning("No price history for this ticker.")
    st.stop()

st.markdown("### Price history (adj close)")
st.plotly_chart(charts.price_chart(prices), use_container_width=True, config={"displayModeBar": False})

c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("### Drawdown")
    st.plotly_chart(
        charts.drawdown_chart(prices), use_container_width=True, config={"displayModeBar": False}
    )
with c2:
    st.markdown("### Pillar profile")
    st.plotly_chart(
        charts.pillar_radar(row), use_container_width=True, config={"displayModeBar": False}
    )
