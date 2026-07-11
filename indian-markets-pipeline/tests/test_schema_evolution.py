"""End-to-end tests for the schema-evolution engine.

Each test spins up an in-memory DuckDB and a temp registry file, then asserts
that an incoming Polars DataFrame produces the expected DDL + registry state +
log entries.
"""

from __future__ import annotations

import duckdb
import polars as pl
import pytest

from markets_pipeline.schema.evolution import ChangeKind, SchemaEvolution
from markets_pipeline.schema.registry import SchemaRegistry


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def registry(tmp_path):
    return SchemaRegistry(tmp_path / "registry.json")


@pytest.fixture
def evo(conn, registry):
    return SchemaEvolution(conn, registry)


def _columns(conn, table: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ?",
        [table],
    ).fetchall()
    return dict(rows)


class TestNewTable:
    def test_creates_table_and_registers(self, evo, conn, registry):
        df = pl.DataFrame({"ticker": ["RELIANCE"], "price": [2500.0]})
        changes = evo.reconcile("stocks", df, primary_key=["ticker"])

        assert len(changes) == 1
        assert changes[0].kind is ChangeKind.NEW_TABLE
        assert changes[0].applied is True

        cols = _columns(conn, "stocks")
        assert cols == {"ticker": "VARCHAR", "price": "DOUBLE"}

        meta = registry.get_table("stocks")
        assert meta is not None
        assert meta["primary_key"] == ["ticker"]
        assert meta["schema_version"] == 1


class TestNoChange:
    def test_identical_schema_produces_no_changes(self, evo):
        df = pl.DataFrame({"ticker": ["RELIANCE"], "price": [2500.0]})
        evo.reconcile("stocks", df, primary_key=["ticker"])

        df2 = pl.DataFrame({"ticker": ["TCS"], "price": [3500.0]})
        changes = evo.reconcile("stocks", df2, primary_key=["ticker"])

        assert changes == []


class TestNewColumn:
    def test_adds_column_to_table_and_registry(self, evo, conn, registry):
        df1 = pl.DataFrame({"ticker": ["RELIANCE"], "price": [2500.0]})
        evo.reconcile("stocks", df1, primary_key=["ticker"])

        df2 = pl.DataFrame(
            {"ticker": ["RELIANCE"], "price": [2500.0], "volume": [1_000_000]}
        )
        changes = evo.reconcile("stocks", df2, primary_key=["ticker"])

        assert len(changes) == 1
        assert changes[0].kind is ChangeKind.NEW_COLUMN
        assert changes[0].column == "volume"
        assert changes[0].applied is True

        assert "volume" in _columns(conn, "stocks")
        meta = registry.get_table("stocks")
        assert "volume" in meta["columns"]
        assert meta["schema_version"] == 2


class TestWidening:
    def test_int32_to_int64_applied(self, evo, conn, registry):
        df1 = pl.DataFrame({"ticker": ["A"], "vol": pl.Series([1], dtype=pl.Int32)})
        evo.reconcile("stocks", df1, primary_key=["ticker"])
        assert _columns(conn, "stocks")["vol"] == "INTEGER"

        df2 = pl.DataFrame({"ticker": ["A"], "vol": pl.Series([1], dtype=pl.Int64)})
        changes = evo.reconcile("stocks", df2, primary_key=["ticker"])

        assert len(changes) == 1
        assert changes[0].kind is ChangeKind.WIDEN_TYPE
        assert changes[0].applied is True
        assert _columns(conn, "stocks")["vol"] == "BIGINT"
        assert registry.get_table("stocks")["columns"]["vol"]["type"] == "BIGINT"


class TestNarrowing:
    def test_bigint_to_int_rejected(self, evo, conn, registry):
        df1 = pl.DataFrame({"ticker": ["A"], "vol": pl.Series([1], dtype=pl.Int64)})
        evo.reconcile("stocks", df1, primary_key=["ticker"])

        df2 = pl.DataFrame({"ticker": ["A"], "vol": pl.Series([1], dtype=pl.Int32)})
        changes = evo.reconcile("stocks", df2, primary_key=["ticker"])

        assert len(changes) == 1
        c = changes[0]
        assert c.kind is ChangeKind.NARROW_TYPE
        assert c.applied is False
        assert c.is_blocking is True
        # DuckDB column type unchanged
        assert _columns(conn, "stocks")["vol"] == "BIGINT"


class TestIncompatible:
    def test_int_to_string_rejected(self, evo, conn):
        df1 = pl.DataFrame({"ticker": ["A"], "vol": pl.Series([1], dtype=pl.Int64)})
        evo.reconcile("stocks", df1, primary_key=["ticker"])

        df2 = pl.DataFrame({"ticker": ["A"], "vol": ["lots"]})
        changes = evo.reconcile("stocks", df2, primary_key=["ticker"])

        assert len(changes) == 1
        assert changes[0].kind is ChangeKind.INCOMPATIBLE_TYPE
        assert changes[0].applied is False
        assert _columns(conn, "stocks")["vol"] == "BIGINT"


class TestEvolutionLog:
    def test_every_change_is_logged(self, evo, conn):
        # 1. new table
        df1 = pl.DataFrame({"ticker": ["A"], "price": [1.0]})
        evo.reconcile("stocks", df1, primary_key=["ticker"])
        # 2. new column
        df2 = pl.DataFrame({"ticker": ["A"], "price": [1.0], "volume": [10]})
        evo.reconcile("stocks", df2, primary_key=["ticker"])
        # 3. narrowing rejected
        df3 = pl.DataFrame(
            {"ticker": ["A"], "price": [1.0], "volume": pl.Series([1], dtype=pl.Int8)}
        )
        evo.reconcile("stocks", df3, primary_key=["ticker"])

        log = conn.execute(
            "SELECT kind, applied FROM _schema_evolution_log ORDER BY event_time"
        ).fetchall()

        kinds = [row[0] for row in log]
        applied = [row[1] for row in log]
        assert kinds == ["new_table", "new_column", "narrow_type"]
        assert applied == [True, True, False]


class TestMultipleChangesAtOnce:
    def test_new_column_plus_widen_in_one_call(self, evo, conn):
        df1 = pl.DataFrame(
            {
                "ticker": ["A"],
                "vol": pl.Series([1], dtype=pl.Int32),
            }
        )
        evo.reconcile("stocks", df1, primary_key=["ticker"])

        df2 = pl.DataFrame(
            {
                "ticker": ["A"],
                "vol": pl.Series([1], dtype=pl.Int64),  # widen
                "exchange": ["NSE"],                     # new
            }
        )
        changes = evo.reconcile("stocks", df2, primary_key=["ticker"])

        kinds = sorted(c.kind.value for c in changes)
        assert kinds == ["new_column", "widen_type"]
        assert all(c.applied for c in changes)
