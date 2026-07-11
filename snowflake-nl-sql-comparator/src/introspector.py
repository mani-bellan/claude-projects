"""Build a SemanticModel from live Snowflake metadata — no hand-written YAML needed.

Reads INFORMATION_SCHEMA for tables/columns/comments, pulls a small sample of rows
per table for example values, and renders the result as YAML in the same
SemanticModel container the curated path uses. Claude gets real schema context for
any database/schema with zero authoring; accuracy is naturally lower than a curated
semantic model because column names alone don't carry business definitions.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import yaml

from .semantic_loader import SemanticModel
from .snowflake_client import SnowflakeClient

MAX_TABLES = 25
SAMPLE_ROWS = 5
MAX_SAMPLE_VALUES = 5
MAX_SAMPLE_VALUE_LEN = 80


def _sample_values(sf: SnowflakeClient, fq_table: str, columns: list[str]) -> dict[str, list[Any]]:
    """One LIMIT-N query per table; distinct per-column values extracted client-side."""
    result = sf.execute(f"SELECT * FROM {fq_table} LIMIT {SAMPLE_ROWS}", row_limit=SAMPLE_ROWS)
    if result.error or result.rows.empty:
        return {}

    samples: dict[str, list[Any]] = {}
    for col in columns:
        if col not in result.rows.columns:
            continue
        seen: list[Any] = []
        for v in result.rows[col]:
            if v is None or v in seen:
                continue
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            elif not isinstance(v, (str, int, float, bool)):
                v = str(v)
            if isinstance(v, str) and len(v) > MAX_SAMPLE_VALUE_LEN:
                v = v[:MAX_SAMPLE_VALUE_LEN] + "…"
            seen.append(v)
            if len(seen) >= MAX_SAMPLE_VALUES:
                break
        if seen:
            samples[col] = seen
    return samples


def introspect(
    sf: SnowflakeClient,
    database: str,
    schema: str,
    max_tables: int = MAX_TABLES,
    with_samples: bool = True,
) -> SemanticModel:
    """Introspect {database}.{schema} into a SemanticModel.

    Raises RuntimeError if the metadata queries fail or the schema has no tables.
    """
    schema_lit = schema.replace("'", "''")

    tables_q = sf.execute(
        f"""
        SELECT table_name, row_count, comment
        FROM {database}.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = '{schema_lit}'
          AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_name
        LIMIT {int(max_tables)}
        """,
        row_limit=max_tables,
    )
    if tables_q.error:
        raise RuntimeError(f"Could not read INFORMATION_SCHEMA.TABLES: {tables_q.error}")
    if tables_q.rows.empty:
        raise RuntimeError(f"No tables or views found in {database}.{schema}.")

    def _opt(v: Any) -> Any:
        # SQL NULL arrives as None or NaN depending on column dtype
        return None if v is None or (isinstance(v, float) and pd.isna(v)) else v

    table_meta = {
        str(r["TABLE_NAME"]): {"row_count": _opt(r["ROW_COUNT"]), "comment": _opt(r["COMMENT"])}
        for _, r in tables_q.rows.iterrows()
    }
    table_names = list(table_meta)
    names_in = ", ".join(f"'{t.replace(chr(39), chr(39) * 2)}'" for t in table_names)

    cols_q = sf.execute(
        f"""
        SELECT table_name, column_name, data_type, comment
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE table_schema = '{schema_lit}'
          AND table_name IN ({names_in})
        ORDER BY table_name, ordinal_position
        """,
        row_limit=10_000,
    )
    if cols_q.error:
        raise RuntimeError(f"Could not read INFORMATION_SCHEMA.COLUMNS: {cols_q.error}")

    tables: list[dict[str, Any]] = []
    for tname in table_names:
        tcols = cols_q.rows[cols_q.rows["TABLE_NAME"] == tname]
        columns = [
            {"name": str(r["COLUMN_NAME"]), "type": str(r["DATA_TYPE"])}
            | ({"description": str(c)} if (c := _opt(r["COMMENT"])) else {})
            for _, r in tcols.iterrows()
        ]

        fq = f"{database}.{schema}.{tname}"
        if with_samples and columns:
            samples = _sample_values(sf, fq, [c["name"] for c in columns])
            for c in columns:
                if c["name"] in samples:
                    c["sample_values"] = samples[c["name"]]

        entry: dict[str, Any] = {
            "name": tname,
            "base_table": {"database": database, "schema": schema, "table": tname},
            "columns": columns,
        }
        meta = table_meta[tname]
        if meta["comment"]:
            entry["description"] = str(meta["comment"])
        if meta["row_count"] is not None:
            entry["row_count"] = int(meta["row_count"])
        tables.append(entry)

    name = f"{database}.{schema} (introspected)"
    description = (
        f"Auto-generated from INFORMATION_SCHEMA of {database}.{schema}: "
        f"{len(tables)} tables/views with column types"
        + (" and sample values." if with_samples else ".")
    )
    parsed = {"name": name, "description": description, "tables": tables}
    raw_yaml = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True, width=120)

    return SemanticModel(
        name=name,
        description=description,
        raw_yaml=raw_yaml,
        parsed=parsed,
        tables=tables,
    )
