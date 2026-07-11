"""Stock and mutual-fund universe lookups.

Stocks: tries to fetch the live Nifty 500 list from NSE; falls back to a
hard-coded Nifty 50 list. Mutual funds: pulls the AMFI master via mfapi.in.
"""

from __future__ import annotations

import io
import logging

import polars as pl
import requests

log = logging.getLogger(__name__)


_NIFTY_500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
_AMFI_SCHEMES_URL = "https://api.mfapi.in/mf"
_HEADERS = {"User-Agent": "Mozilla/5.0 markets-pipeline/0.1"}


# Hard-coded Nifty 50 tickers (NSE symbols + .NS suffix for yfinance).
# Used as fallback if the NSE CSV fetch fails.
NIFTY_50_FALLBACK: list[str] = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "BAJFINANCE.NS",
    "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "NTPC.NS", "M&M.NS", "POWERGRID.NS", "NESTLEIND.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "GRASIM.NS",
    "TECHM.NS", "ONGC.NS", "COALINDIA.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS",
    "DRREDDY.NS", "CIPLA.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS",
    "BRITANNIA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "HINDALCO.NS", "BPCL.NS",
    "TATACONSUM.NS", "UPL.NS", "SBILIFE.NS", "HDFCLIFE.NS", "LTIM.NS",
]


def fetch_nifty_500_tickers() -> list[str]:
    """Fetch the live Nifty 500 list from NSE. Falls back to Nifty 50 on failure."""
    try:
        r = requests.get(_NIFTY_500_URL, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        df = pl.read_csv(io.BytesIO(r.content))
        symbols = df["Symbol"].to_list()
        return [f"{s.strip()}.NS" for s in symbols if s and s.strip()]
    except Exception as e:
        log.warning("NSE Nifty 500 fetch failed (%s); using Nifty 50 fallback", e)
        return NIFTY_50_FALLBACK


def get_stock_universe(name: str = "NIFTY_500") -> list[str]:
    name = name.upper()
    if name == "NIFTY_50":
        return NIFTY_50_FALLBACK
    if name == "NIFTY_500":
        return fetch_nifty_500_tickers()
    raise ValueError(f"Unknown universe: {name}")


def fetch_mf_scheme_master() -> pl.DataFrame:
    """All AMFI mutual fund schemes via mfapi.in. Columns: scheme_code, scheme_name."""
    r = requests.get(_AMFI_SCHEMES_URL, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()  # list of {schemeCode, schemeName}
    return pl.DataFrame(
        {
            "scheme_code": [int(x["schemeCode"]) for x in rows],
            "scheme_name": [x["schemeName"] for x in rows],
        }
    )
