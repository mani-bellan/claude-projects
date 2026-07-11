"""Schema-aware DuckDB loader.

Every call:
  1. Reconciles schema (creates table / adds column / widens type / rejects).
  2. If any column triggered a *blocking* change, the entire batch is routed
     to `_rejects_<table>` and the live table is left untouched. This is the
     conservative choice: a single bad column shouldn't pollute history.
  3. Otherwise performs an idempotent upsert keyed by primary_key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import duckdb
import polars as pl

from ..schema.evolution import SchemaChange, SchemaEvolution

log = logging.getLogger(__name__)


@dataclass
class LoadResult:
    table: str
    rows_in: int
    rows_loaded: int
    rows_rejected: int
    schema_changes: list[SchemaChange] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.rows_rejected == 0


class DuckDBLoader:
    def __init__(self, conn: duckdb.DuckDBPyConnection, evolution: SchemaEvolution):
        self.conn = conn
        self.evolution = evolution

    def load(
        self,
        table: str,
        df: pl.DataFrame,
        primary_key: list[str],
    ) -> LoadResult:
        rows_in = df.height

        if rows_in == 0:
            log.info("Empty batch for %s; skipping", table)
            return LoadResult(table=table, rows_in=0, rows_loaded=0, rows_rejected=0)

        changes = self.evolution.reconcile(table, df, primary_key)
        blocking = [c for c in changes if c.is_blocking]

        if blocking:
            log.warning(
                "Schema conflict on %s (%s); quarantining %s rows",
                table,
                ", ".join(f"{c.column}:{c.kind.value}" for c in blocking),
                rows_in,
            )
            self._quarantine(table, df)
            return LoadResult(
                table=table,
                rows_in=rows_in,
                rows_loaded=0,
                rows_rejected=rows_in,
                schema_changes=changes,
            )

        loaded = self._upsert(table, df, primary_key)
        log.info("Loaded %s rows into %s (%s schema changes)", loaded, table, len(changes))
        return LoadResult(
            table=table,
            rows_in=rows_in,
            rows_loaded=loaded,
            rows_rejected=0,
            schema_changes=changes,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _upsert(self, table: str, df: pl.DataFrame, primary_key: list[str]) -> int:
        cols = df.columns
        col_list = ", ".join(f'"{c}"' for c in cols)
        join_predicate = " AND ".join(
            f'"{table}"."{c}" = incoming."{c}"' for c in primary_key
        )

        self.conn.register("incoming", df)
        try:
            self.conn.execute("BEGIN")
            if primary_key:
                self.conn.execute(
                    f'DELETE FROM "{table}" USING incoming WHERE {join_predicate}'
                )
            self.conn.execute(
                f'INSERT INTO "{table}" ({col_list}) SELECT {col_list} FROM incoming'
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.unregister("incoming")

        return df.height

    def _quarantine(self, table: str, df: pl.DataFrame) -> None:
        """Append the offending batch to `_rejects_<table>` (created on demand).

        The quarantine table mirrors the *incoming* schema, not the registered one.
        That way operators can inspect what actually arrived.
        """
        reject_table = f"_rejects_{table}"
        self.conn.register("rejects", df)
        try:
            # CREATE TABLE AS preserves types from the Polars frame.
            exists = self.conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                [reject_table],
            ).fetchone()
            if not exists:
                self.conn.execute(
                    f'CREATE TABLE "{reject_table}" AS SELECT *, '
                    f"current_timestamp AS _rejected_at FROM rejects"
                )
            else:
                self.conn.execute(
                    f'INSERT INTO "{reject_table}" SELECT *, '
                    f"current_timestamp AS _rejected_at FROM rejects"
                )
        finally:
            self.conn.unregister("rejects")
