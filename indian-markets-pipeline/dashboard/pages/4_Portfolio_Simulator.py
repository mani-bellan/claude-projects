"""Backtest a monthly SIP into a chosen instrument over historical data."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_DASHBOARD = Path(__file__).resolve().parents[1]
if str(_DASHBOARD) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD))

import numpy as np
import polars as pl
import streamlit as st
from scipy.optimize import brentq

from components import charts, data, styling

st.set_page_config(page_title="Portfolio Simulator", page_icon="🧪", layout="wide")
styling.apply()

st.markdown("# Portfolio Simulator")
st.markdown("Backtest a monthly SIP into a chosen instrument over historical data.")
styling.disclaimer()

# ---- Inputs ---------------------------------------------------------------

with st.sidebar:
    st.markdown("### Setup")
    instrument_kind = st.radio("Instrument", ["Stock", "Mutual Fund"], horizontal=True)
    monthly = st.number_input(
        "Monthly investment (₹)", min_value=500, max_value=200_000, value=10_000, step=500
    )
    years = st.slider("Horizon (years, historical lookback)", 1, 20, 10)


def _xirr(flows: list[tuple[date, float]]) -> float:
    """Compute XIRR (annualized IRR for irregular cash flows)."""
    if not flows:
        return float("nan")
    t0 = flows[0][0]

    def npv(rate):
        return sum(amt / (1 + rate) ** ((d - t0).days / 365.0) for d, amt in flows)

    try:
        return brentq(npv, -0.99, 10.0)
    except ValueError:
        return float("nan")


def _simulate_sip(prices: pl.DataFrame, value_col: str, monthly_amount: float) -> dict:
    """SIP at the first available price each month. Returns timeline + summary."""
    if prices.is_empty():
        return {}
    df = prices.sort("date").with_columns(
        pl.col("date").dt.year().alias("y"), pl.col("date").dt.month().alias("m")
    )
    monthlies = (
        df.group_by(["y", "m"])
        .agg([pl.col("date").min().alias("date"), pl.col(value_col).first().alias("price")])
        .sort("date")
    )
    if monthlies.is_empty():
        return {}

    units = 0.0
    invested = 0.0
    flows: list[tuple[date, float]] = []
    rows = []
    for r in monthlies.iter_rows(named=True):
        if r["price"] is None or r["price"] <= 0:
            continue
        units += monthly_amount / r["price"]
        invested += monthly_amount
        flows.append((r["date"], -monthly_amount))
        rows.append({"date": r["date"], "invested": invested, "value": units * r["price"]})

    last = df.tail(1).row(0, named=True)
    final_value = units * last[value_col]
    flows.append((last["date"], final_value))

    timeline = pl.DataFrame(rows)
    return {
        "timeline": timeline,
        "invested": invested,
        "final_value": final_value,
        "xirr": _xirr(flows),
        "units": units,
    }


# ---- Pick instrument -------------------------------------------------------

if instrument_kind == "Stock":
    stocks = data.stock_recommendations()
    if stocks.is_empty():
        st.info("No stock data yet.")
        st.stop()
    ticker = st.selectbox("Stock", options=stocks.sort("rank")["ticker"].to_list())
    prices = data.stock_prices(ticker)
    value_col = "adj_close"
    label = ticker
else:
    mfs = data.mf_recommendations()
    if mfs.is_empty():
        st.info("No mutual fund data yet.")
        st.stop()
    choice = st.selectbox(
        "Scheme",
        options=mfs.sort("rank")["scheme_code"].to_list(),
        format_func=lambda code: mfs.filter(pl.col("scheme_code") == code)["scheme_name"][0],
    )
    prices = data.mf_navs(choice)
    value_col = "nav"
    label = mfs.filter(pl.col("scheme_code") == choice)["scheme_name"][0]

# Restrict to lookback window
cutoff = date.today() - timedelta(days=365 * years)
prices = prices.filter(pl.col("date") >= cutoff)
if prices.is_empty():
    st.warning(f"Not enough history for a {years}-year backtest.")
    st.stop()

result = _simulate_sip(prices, value_col, monthly)
if not result:
    st.warning("Simulation failed — try a different instrument.")
    st.stop()

# ---- Results --------------------------------------------------------------

cols = st.columns(4)
cols[0].metric("Invested", f"₹{result['invested']:,.0f}")
cols[1].metric("Final value", f"₹{result['final_value']:,.0f}", f"{(result['final_value']/result['invested']-1)*100:+.1f}%")
xirr = result["xirr"]
cols[2].metric("XIRR", f"{xirr*100:.1f}%/yr" if not np.isnan(xirr) else "—")
cols[3].metric("Units", f"{result['units']:,.2f}")

st.markdown(f"### {label} — wealth curve")
st.plotly_chart(
    charts.wealth_chart(result["timeline"]),
    use_container_width=True,
    config={"displayModeBar": False},
)
