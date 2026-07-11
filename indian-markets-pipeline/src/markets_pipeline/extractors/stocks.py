"""Stock OHLCV extractor backed by yfinance.

Returns a long-format Polars DataFrame: one row per (ticker, date).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import polars as pl
import yfinance as yf

log = logging.getLogger(__name__)


_OUTPUT_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]


def fetch_prices(
    tickers: list[str],
    start: date | None = None,
    end: date | None = None,
    chunk_size: int = 25,
) -> pl.DataFrame:
    """Download daily OHLCV for `tickers` between `start` and `end` (inclusive).

    yfinance returns wide-format DataFrames (columns multi-indexed by ticker);
    we melt to long format so the warehouse layout is `(ticker, date) -> values`.
    """
    if not tickers:
        return pl.DataFrame(schema=_long_schema())

    end = end or date.today()
    start = start or (end - timedelta(days=365 * 20))

    frames: list[pl.DataFrame] = []
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i : i + chunk_size]
        log.info("yfinance: fetching %s tickers (%s..%s)", len(chunk), start, end)
        try:
            wide = yf.download(
                tickers=chunk,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as e:
            log.warning("yfinance chunk failed: %s", e)
            continue
        if wide is None or wide.empty:
            continue
        frames.append(_melt_yf(wide, chunk))

    if not frames:
        return pl.DataFrame(schema=_long_schema())

    out = pl.concat(frames, how="vertical_relaxed")
    return out.unique(subset=["ticker", "date"], keep="last").sort(["ticker", "date"])


def _long_schema() -> dict:
    return {
        "ticker": pl.Utf8,
        "date": pl.Date,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "adj_close": pl.Float64,
        "volume": pl.Int64,
    }


def _melt_yf(wide, tickers: list[str]) -> pl.DataFrame:
    """Convert yfinance multi-index pandas frame to long-format Polars."""
    import pandas as pd

    if isinstance(wide.columns, pd.MultiIndex):
        per_ticker = []
        for t in tickers:
            if t not in wide.columns.get_level_values(0):
                continue
            sub = wide[t].reset_index().assign(ticker=t)
            per_ticker.append(sub)
        if not per_ticker:
            return pl.DataFrame(schema=_long_schema())
        flat = pd.concat(per_ticker, ignore_index=True)
    else:
        # Single-ticker call — columns are flat.
        flat = wide.reset_index().assign(ticker=tickers[0])

    # Normalize column names from yfinance variants.
    rename = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    flat = flat.rename(columns=rename)
    flat = flat[["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]]
    flat = flat.dropna(subset=["close"])

    df = pl.from_pandas(flat)
    return df.with_columns(
        pl.col("date").cast(pl.Date),
        pl.col("volume").cast(pl.Int64, strict=False),
    ).select(_OUTPUT_COLUMNS)
