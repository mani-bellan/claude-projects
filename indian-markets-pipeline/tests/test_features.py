"""Feature-engineering tests with synthetic price series."""

from __future__ import annotations

import math
from datetime import date, timedelta

import duckdb
import polars as pl
import pytest

from markets_pipeline.transformers import features


def _seed_stock_prices(conn, ticker: str, prices: list[tuple[date, float]]):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS stock_prices (ticker VARCHAR, date DATE, adj_close DOUBLE)"
    )
    for d, p in prices:
        conn.execute(
            "INSERT INTO stock_prices (ticker, date, adj_close) VALUES (?, ?, ?)",
            [ticker, d, p],
        )


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


class TestCAGR:
    def test_doubling_over_5_years_gives_about_15_percent(self, conn):
        # Build a 5-year (~1825 day) ramp from 100 -> 200 with daily prices.
        start = date(2019, 1, 1)
        days = 365 * 5
        series = [(start + timedelta(days=i), 100.0 * (2.0 ** (i / days))) for i in range(days + 1)]
        _seed_stock_prices(conn, "X", series)

        f = features.compute_stock_features(conn)
        cagr = f.filter(pl.col("ticker") == "X")["cagr_5y"][0]
        assert math.isclose(cagr, 2 ** (1 / 5) - 1, abs_tol=0.005)


class TestVolatility:
    def test_constant_price_has_zero_volatility(self, conn):
        series = [(date(2024, 1, 1) + timedelta(days=i), 100.0) for i in range(60)]
        _seed_stock_prices(conn, "FLAT", series)

        f = features.compute_stock_features(conn)
        vol = f.filter(pl.col("ticker") == "FLAT")["volatility"][0]
        assert vol == 0.0 or vol is None or math.isclose(vol, 0.0, abs_tol=1e-9)


class TestMaxDrawdown:
    def test_50_percent_drop_from_peak_recovers(self, conn):
        start = date(2024, 1, 1)
        # 100 -> 200 -> 100 -> 150
        prices = (
            [(start + timedelta(days=i), 100.0 + i) for i in range(101)]
            + [(start + timedelta(days=101 + i), 200.0 - i) for i in range(101)]
            + [(start + timedelta(days=202 + i), 100.0 + i * 0.5) for i in range(101)]
        )
        _seed_stock_prices(conn, "Y", prices)

        f = features.compute_stock_features(conn)
        dd = f.filter(pl.col("ticker") == "Y")["max_drawdown"][0]
        # Peak at 200, trough at 100 -> 50% drawdown
        assert math.isclose(dd, -0.50, abs_tol=0.005)


class TestEmpty:
    def test_empty_input_returns_empty_df(self, conn):
        conn.execute("CREATE TABLE stock_prices (ticker VARCHAR, date DATE, adj_close DOUBLE)")
        f = features.compute_stock_features(conn)
        assert f.is_empty()


class TestShortHistorySkipsLongCagr:
    def test_six_months_of_data_yields_null_cagr_5y(self, conn):
        start = date(2024, 1, 1)
        series = [(start + timedelta(days=i), 100.0 * (1.001 ** i)) for i in range(180)]
        _seed_stock_prices(conn, "Z", series)

        f = features.compute_stock_features(conn)
        row = f.filter(pl.col("ticker") == "Z")
        assert row["cagr_5y"][0] is None
        assert row["cagr_3y"][0] is None
