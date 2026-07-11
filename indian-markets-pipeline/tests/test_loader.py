"""Loader tests — schema reconcile + upsert + quarantine."""

from __future__ import annotations

from datetime import date

import duckdb
import polars as pl
import pytest

from markets_pipeline.loaders import DuckDBLoader
from markets_pipeline.schema import SchemaEvolution, SchemaRegistry


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def loader(conn, tmp_path):
    registry = SchemaRegistry(tmp_path / "registry.json")
    evo = SchemaEvolution(conn, registry)
    return DuckDBLoader(conn, evo)


class TestFreshLoad:
    def test_creates_table_and_loads_rows(self, loader, conn):
        df = pl.DataFrame(
            {
                "ticker": ["A", "B"],
                "date": [date(2024, 1, 1), date(2024, 1, 1)],
                "close": [1.0, 2.0],
            }
        )
        result = loader.load("stock_prices", df, primary_key=["ticker", "date"])
        assert result.ok
        assert result.rows_loaded == 2
        n = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]
        assert n == 2


class TestUpsert:
    def test_re_inserting_same_pk_replaces_rows(self, loader, conn):
        df1 = pl.DataFrame(
            {"ticker": ["A"], "date": [date(2024, 1, 1)], "close": [100.0]}
        )
        loader.load("stock_prices", df1, primary_key=["ticker", "date"])

        df2 = pl.DataFrame(
            {"ticker": ["A"], "date": [date(2024, 1, 1)], "close": [105.0]}
        )
        result = loader.load("stock_prices", df2, primary_key=["ticker", "date"])

        assert result.rows_loaded == 1
        n = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]
        assert n == 1
        close = conn.execute("SELECT close FROM stock_prices").fetchone()[0]
        assert close == 105.0


class TestQuarantine:
    def test_incompatible_change_routes_batch_to_rejects(self, loader, conn):
        df1 = pl.DataFrame(
            {
                "ticker": ["A"],
                "date": [date(2024, 1, 1)],
                "volume": pl.Series([100], dtype=pl.Int64),
            }
        )
        loader.load("stock_prices", df1, primary_key=["ticker", "date"])

        # Volume now arriving as a string — incompatible.
        df2 = pl.DataFrame(
            {"ticker": ["B"], "date": [date(2024, 1, 2)], "volume": ["lots"]}
        )
        result = loader.load("stock_prices", df2, primary_key=["ticker", "date"])

        assert result.rows_loaded == 0
        assert result.rows_rejected == 1
        assert not result.ok

        n = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]
        assert n == 1

        rejected = conn.execute("SELECT COUNT(*) FROM _rejects_stock_prices").fetchone()[0]
        assert rejected == 1


class TestEmptyBatch:
    def test_empty_batch_is_a_noop(self, loader):
        df = pl.DataFrame(
            schema={"ticker": pl.Utf8, "date": pl.Date, "close": pl.Float64}
        )
        result = loader.load("stock_prices", df, primary_key=["ticker", "date"])
        assert result.rows_in == 0
        assert result.rows_loaded == 0
        assert result.ok


class TestNewColumnPropagates:
    def test_added_column_is_visible_after_load(self, loader, conn):
        df1 = pl.DataFrame(
            {"ticker": ["A"], "date": [date(2024, 1, 1)], "close": [1.0]}
        )
        loader.load("stock_prices", df1, primary_key=["ticker", "date"])

        df2 = pl.DataFrame(
            {
                "ticker": ["A"],
                "date": [date(2024, 1, 2)],
                "close": [2.0],
                "volume": [1000],
            }
        )
        result = loader.load("stock_prices", df2, primary_key=["ticker", "date"])
        assert result.ok
        kinds = [c.kind.value for c in result.schema_changes]
        assert "new_column" in kinds

        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'stock_prices'"
        ).fetchall()
        assert "volume" in {c[0] for c in cols}
