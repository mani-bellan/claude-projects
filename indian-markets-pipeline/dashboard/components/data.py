"""DuckDB read helpers for the dashboard.

Connection is opened read-only and cached for the Streamlit process so
multiple page renders share it. Query results are cached for 5 minutes.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl
import streamlit as st


# Ensure the local `src/` layout is importable when running `streamlit run`.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _duckdb_path() -> Path:
    raw = os.getenv("DUCKDB_PATH", "data/markets.duckdb")
    return Path(raw) if Path(raw).is_absolute() else _PROJECT_ROOT / raw


@st.cache_resource(show_spinner=False)
def get_conn() -> duckdb.DuckDBPyConnection:
    path = _duckdb_path()
    if not path.exists():
        raise FileNotFoundError(
            f"DuckDB warehouse not found at {path}. "
            "Run `make backfill` or the smoke pipeline first."
        )
    return duckdb.connect(str(path), read_only=True)


def _table_exists(name: str) -> bool:
    rows = get_conn().execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = ? AND table_schema = 'main'",
        [name],
    ).fetchone()
    return rows is not None


@st.cache_data(ttl=300, show_spinner=False)
def stock_recommendations() -> pl.DataFrame:
    if not _table_exists("stock_recommendations"):
        return pl.DataFrame()
    return get_conn().execute(
        "SELECT * FROM stock_recommendations ORDER BY rank"
    ).pl()


@st.cache_data(ttl=300, show_spinner=False)
def mf_recommendations() -> pl.DataFrame:
    if not _table_exists("mf_recommendations"):
        return pl.DataFrame()
    return get_conn().execute(
        "SELECT * FROM mf_recommendations ORDER BY rank"
    ).pl()


@st.cache_data(ttl=300, show_spinner=False)
def stock_prices(ticker: str) -> pl.DataFrame:
    return get_conn().execute(
        "SELECT date, close, adj_close, volume FROM stock_prices "
        "WHERE ticker = ? ORDER BY date",
        [ticker],
    ).pl()


@st.cache_data(ttl=300, show_spinner=False)
def mf_navs(scheme_code: int) -> pl.DataFrame:
    return get_conn().execute(
        "SELECT date, nav FROM mf_navs WHERE scheme_code = ? ORDER BY date",
        [scheme_code],
    ).pl()


@st.cache_data(ttl=300, show_spinner=False)
def stock_features() -> pl.DataFrame:
    if not _table_exists("stock_features"):
        return pl.DataFrame()
    return get_conn().execute("SELECT * FROM stock_features").pl()


@st.cache_data(ttl=300, show_spinner=False)
def freshness() -> dict:
    """Latest dates loaded into the warehouse — drives the home-page status panel."""
    out = {"stock_prices": None, "mf_navs": None, "computed_at": None}
    if _table_exists("stock_prices"):
        out["stock_prices"] = get_conn().execute(
            "SELECT MAX(date) FROM stock_prices"
        ).fetchone()[0]
    if _table_exists("mf_navs"):
        out["mf_navs"] = get_conn().execute(
            "SELECT MAX(date) FROM mf_navs"
        ).fetchone()[0]
    if _table_exists("stock_recommendations"):
        out["computed_at"] = get_conn().execute(
            "SELECT MAX(computed_at) FROM stock_recommendations"
        ).fetchone()[0]
    return out


@st.cache_data(ttl=300, show_spinner=False)
def row_counts() -> dict:
    counts = {}
    for t in ("stock_prices", "mf_navs", "stock_recommendations", "mf_recommendations"):
        if _table_exists(t):
            counts[t] = get_conn().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        else:
            counts[t] = 0
    return counts
