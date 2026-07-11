"""Per-instrument feature engineering.

Computes CAGR (multiple windows), annualized volatility, Sharpe ratio, and
max drawdown for each ticker (stocks) or scheme_code (mutual funds).

`compute_stock_features` and `compute_mf_features` accept an open DuckDB
connection and return a Polars DataFrame ready to load via `DuckDBLoader`.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import duckdb
import polars as pl

# Stocks: business-day series. Mutual fund NAVs are calendar-day.
TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365

# Approximate India 10y G-Sec yield. Configurable per call.
DEFAULT_RISK_FREE_RATE = 0.06


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def compute_stock_features(
    conn: duckdb.DuckDBPyConnection,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> pl.DataFrame:
    df = conn.execute(
        "SELECT ticker, date, adj_close FROM stock_prices "
        "WHERE adj_close IS NOT NULL ORDER BY ticker, date"
    ).pl()
    if df.is_empty():
        return _empty_features("ticker")

    feats = _compute_features(
        df,
        key="ticker",
        price_col="adj_close",
        periods_per_year=TRADING_DAYS_PER_YEAR,
        risk_free_rate=risk_free_rate,
    )
    return feats.with_columns(pl.lit(None, dtype=pl.Utf8).alias("_unused")).drop("_unused")


def compute_mf_features(
    conn: duckdb.DuckDBPyConnection,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> pl.DataFrame:
    df = conn.execute(
        "SELECT scheme_code, scheme_name, scheme_category, fund_house, date, nav "
        "FROM mf_navs WHERE nav IS NOT NULL ORDER BY scheme_code, date"
    ).pl()
    if df.is_empty():
        return _empty_features("scheme_code", extra={"scheme_name": pl.Utf8, "scheme_category": pl.Utf8, "fund_house": pl.Utf8})

    metrics = _compute_features(
        df.select(["scheme_code", "date", "nav"]),
        key="scheme_code",
        price_col="nav",
        periods_per_year=CALENDAR_DAYS_PER_YEAR,
        risk_free_rate=risk_free_rate,
    )
    meta = df.group_by("scheme_code").agg(
        [
            pl.col("scheme_name").first(),
            pl.col("scheme_category").first(),
            pl.col("fund_house").first(),
        ]
    )
    return metrics.join(meta, on="scheme_code", how="left")


# ---------------------------------------------------------------------------
# Core math
# ---------------------------------------------------------------------------


def _compute_features(
    df: pl.DataFrame,
    key: str,
    price_col: str,
    periods_per_year: int,
    risk_free_rate: float,
) -> pl.DataFrame:
    df = df.sort([key, "date"]).with_columns(
        pl.col(price_col).log().diff().over(key).alias("log_return")
    )

    base = df.group_by(key).agg(
        [
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            pl.col(price_col).last().alias("latest_price"),
            pl.col("log_return").drop_nulls().std().alias("_daily_vol"),
            pl.col("log_return").drop_nulls().mean().alias("_daily_mean"),
            pl.col(price_col).count().alias("observations"),
        ]
    )

    base = base.with_columns(
        [
            (pl.col("_daily_vol") * math.sqrt(periods_per_year)).alias("volatility"),
            ((pl.col("_daily_mean") * periods_per_year).exp() - 1).alias("annualized_return"),
            (
                (pl.col("last_date") - pl.col("first_date")).dt.total_days() / 365.0
            ).alias("years_history"),
        ]
    ).with_columns(
        pl.when(pl.col("volatility") > 0)
        .then((pl.col("annualized_return") - risk_free_rate) / pl.col("volatility"))
        .otherwise(None)
        .alias("sharpe")
    )

    drawdown = (
        df.with_columns(pl.col(price_col).cum_max().over(key).alias("_peak"))
        .with_columns(((pl.col(price_col) - pl.col("_peak")) / pl.col("_peak")).alias("_dd"))
        .group_by(key)
        .agg(pl.col("_dd").min().alias("max_drawdown"))
    )

    out = base.join(drawdown, on=key, how="left")
    for years in (1, 3, 5, 10):
        out = out.join(_cagr_window(df, key, price_col, years), on=key, how="left")

    return out.select(
        [
            key,
            "first_date",
            "last_date",
            "observations",
            "years_history",
            "latest_price",
            "annualized_return",
            "volatility",
            "sharpe",
            "max_drawdown",
            "cagr_1y",
            "cagr_3y",
            "cagr_5y",
            "cagr_10y",
        ]
    ).with_columns(pl.lit(_now_ts()).alias("computed_at"))


def _cagr_window(
    df: pl.DataFrame, key: str, price_col: str, years: int
) -> pl.DataFrame:
    """CAGR over the trailing N years per `key`. NULL when history is too short."""
    max_date: date = df["date"].max()
    cutoff = max_date - timedelta(days=365 * years)

    window = df.filter(pl.col("date") >= cutoff).sort([key, "date"])
    agg = window.group_by(key).agg(
        [
            pl.col("date").min().alias("_w_start"),
            pl.col("date").max().alias("_w_end"),
            pl.col(price_col).first().alias("_w_first"),
            pl.col(price_col).last().alias("_w_last"),
        ]
    )

    # Require at least 90% of the requested window to qualify.
    min_days = int(years * 365 * 0.9)
    return agg.with_columns(
        pl.when(
            ((pl.col("_w_end") - pl.col("_w_start")).dt.total_days() >= min_days)
            & (pl.col("_w_first") > 0)
        )
        .then((pl.col("_w_last") / pl.col("_w_first")).pow(1.0 / years) - 1)
        .otherwise(None)
        .alias(f"cagr_{years}y")
    ).select([key, f"cagr_{years}y"])


def _empty_features(key: str, extra: dict | None = None) -> pl.DataFrame:
    schema = {
        key: pl.Utf8 if key == "ticker" else pl.Int64,
        "first_date": pl.Date,
        "last_date": pl.Date,
        "observations": pl.Int64,
        "years_history": pl.Float64,
        "latest_price": pl.Float64,
        "annualized_return": pl.Float64,
        "volatility": pl.Float64,
        "sharpe": pl.Float64,
        "max_drawdown": pl.Float64,
        "cagr_1y": pl.Float64,
        "cagr_3y": pl.Float64,
        "cagr_5y": pl.Float64,
        "cagr_10y": pl.Float64,
        "computed_at": pl.Datetime,
    }
    if extra:
        schema.update(extra)
    return pl.DataFrame(schema=schema)


def _now_ts():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)
