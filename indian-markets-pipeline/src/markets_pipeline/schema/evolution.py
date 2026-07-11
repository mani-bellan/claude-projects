"""Schema evolution engine.

`SchemaEvolution.reconcile(table, df, primary_key)` is the single entry point
every loader uses before writing data. It:

  1. Compares the incoming DataFrame schema to the registered schema.
  2. Applies safe DDL changes to DuckDB and updates the registry.
  3. Rejects unsafe changes (narrowing, incompatible families).
  4. Logs every event — applied or rejected — to `_schema_evolution_log`.

The loader is then responsible for routing rejected rows to a quarantine table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import duckdb
import polars as pl

from .registry import SchemaRegistry
from .types import TypeCompatibility, compare_types, polars_to_duckdb


class ChangeKind(Enum):
    NEW_TABLE = "new_table"
    NEW_COLUMN = "new_column"
    WIDEN_TYPE = "widen_type"
    NARROW_TYPE = "narrow_type"
    INCOMPATIBLE_TYPE = "incompatible_type"
    NO_CHANGE = "no_change"


@dataclass
class SchemaChange:
    kind: ChangeKind
    table: str
    column: str | None = None
    old_type: str | None = None
    new_type: str | None = None
    applied: bool = False
    note: str = ""

    @property
    def is_blocking(self) -> bool:
        """Changes the loader must route around (quarantine)."""
        return self.kind in {ChangeKind.NARROW_TYPE, ChangeKind.INCOMPATIBLE_TYPE}


_LOG_TABLE = "_schema_evolution_log"


class SchemaEvolution:
    def __init__(self, conn: duckdb.DuckDBPyConnection, registry: SchemaRegistry):
        self.conn = conn
        self.registry = registry
        self._ensure_log_table()

    def _ensure_log_table(self) -> None:
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_LOG_TABLE} (
                event_time  TIMESTAMP,
                table_name  VARCHAR,
                column_name VARCHAR,
                kind        VARCHAR,
                old_type    VARCHAR,
                new_type    VARCHAR,
                applied     BOOLEAN,
                note        VARCHAR
            )
            """
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconcile(
        self,
        table: str,
        df: pl.DataFrame,
        primary_key: list[str],
    ) -> list[SchemaChange]:
        """Bring DuckDB + registry into sync with `df`'s schema. Return all changes."""
        incoming_cols = {col: polars_to_duckdb(df[col].dtype) for col in df.columns}
        registered = self.registry.get_table(table)

        if registered is None:
            return [self._create_new_table(table, incoming_cols, primary_key)]

        registered_cols: dict[str, str] = {
            c: meta["type"] for c, meta in registered["columns"].items()
        }
        changes: list[SchemaChange] = []

        for col, new_type in incoming_cols.items():
            if col not in registered_cols:
                changes.append(self._add_new_column(table, col, new_type))
                continue

            compat = compare_types(registered_cols[col], new_type)
            if compat is TypeCompatibility.IDENTICAL:
                continue
            if compat is TypeCompatibility.WIDENING:
                changes.append(self._widen_column(table, col, registered_cols[col], new_type))
            elif compat is TypeCompatibility.NARROWING:
                changes.append(
                    self._reject(
                        ChangeKind.NARROW_TYPE,
                        table,
                        col,
                        registered_cols[col],
                        new_type,
                        "Narrowing change rejected; rows quarantined",
                    )
                )
            else:
                changes.append(
                    self._reject(
                        ChangeKind.INCOMPATIBLE_TYPE,
                        table,
                        col,
                        registered_cols[col],
                        new_type,
                        "Type families incompatible; rows quarantined",
                    )
                )

        return changes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_new_table(
        self, table: str, columns: dict[str, str], primary_key: list[str]
    ) -> SchemaChange:
        cols_sql = ", ".join(f'"{c}" {t}' for c, t in columns.items())
        if primary_key:
            pk_cols = ", ".join('"' + c + '"' for c in primary_key)
            pk_sql = f", PRIMARY KEY ({pk_cols})"
        else:
            pk_sql = ""
        self.conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({cols_sql}{pk_sql})')
        self.registry.register_table(
            table,
            columns={c: {"type": t, "nullable": True} for c, t in columns.items()},
            primary_key=primary_key,
        )
        change = SchemaChange(kind=ChangeKind.NEW_TABLE, table=table, applied=True)
        self._log(change)
        return change

    def _add_new_column(self, table: str, column: str, type_: str) -> SchemaChange:
        self.conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {type_}')
        self.registry.add_column(table, column, type_)
        change = SchemaChange(
            kind=ChangeKind.NEW_COLUMN,
            table=table,
            column=column,
            new_type=type_,
            applied=True,
        )
        self._log(change)
        return change

    def _widen_column(
        self, table: str, column: str, old_type: str, new_type: str
    ) -> SchemaChange:
        self.conn.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE {new_type}')
        self.registry.update_column_type(table, column, new_type)
        change = SchemaChange(
            kind=ChangeKind.WIDEN_TYPE,
            table=table,
            column=column,
            old_type=old_type,
            new_type=new_type,
            applied=True,
        )
        self._log(change)
        return change

    def _reject(
        self,
        kind: ChangeKind,
        table: str,
        column: str,
        old_type: str,
        new_type: str,
        note: str,
    ) -> SchemaChange:
        change = SchemaChange(
            kind=kind,
            table=table,
            column=column,
            old_type=old_type,
            new_type=new_type,
            applied=False,
            note=note,
        )
        self._log(change)
        return change

    def _log(self, change: SchemaChange) -> None:
        self.conn.execute(
            f"INSERT INTO {_LOG_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                datetime.now(timezone.utc),
                change.table,
                change.column,
                change.kind.value,
                change.old_type,
                change.new_type,
                change.applied,
                change.note,
            ],
        )
