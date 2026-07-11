"""DuckDB type compatibility logic.

A small but load-bearing module: the rules here decide whether an incoming
schema change is safe to auto-apply, or must be quarantined.
"""

from __future__ import annotations

from enum import Enum

import polars as pl


class TypeCompatibility(Enum):
    IDENTICAL = "identical"
    WIDENING = "widening"          # safe auto-promote (INTEGER -> BIGINT)
    NARROWING = "narrowing"        # potential data loss — reject
    INCOMPATIBLE = "incompatible"  # different families — reject


# Ordered by representational width within the numeric family.
# Floats are placed after ints because writing an int into a float column is lossless,
# but writing a float into an int column is not.
_NUMERIC_ORDER: list[str] = [
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "FLOAT",
    "DOUBLE",
]

_STRING_TYPES = {"VARCHAR", "TEXT", "STRING", "CHAR"}
_TEMPORAL_TYPES = {"DATE", "TIMESTAMP", "TIMESTAMPTZ", "TIME"}

_ALIASES = {
    "INT": "INTEGER",
    "INT4": "INTEGER",
    "INT8": "BIGINT",
    "REAL": "FLOAT",
    "FLOAT4": "FLOAT",
    "FLOAT8": "DOUBLE",
    "DOUBLE PRECISION": "DOUBLE",
}


def normalize_type(t: str) -> str:
    """Strip parameters (e.g. VARCHAR(50) -> VARCHAR), apply DuckDB aliases."""
    t = t.upper().strip()
    if "(" in t:
        t = t.split("(", 1)[0].strip()
    return _ALIASES.get(t, t)


def compare_types(old: str, new: str) -> TypeCompatibility:
    """Classify a proposed change from `old` to `new` DuckDB type."""
    old_n = normalize_type(old)
    new_n = normalize_type(new)

    if old_n == new_n:
        return TypeCompatibility.IDENTICAL

    if old_n in _NUMERIC_ORDER and new_n in _NUMERIC_ORDER:
        if _NUMERIC_ORDER.index(new_n) > _NUMERIC_ORDER.index(old_n):
            return TypeCompatibility.WIDENING
        return TypeCompatibility.NARROWING

    if old_n in _STRING_TYPES and new_n in _STRING_TYPES:
        return TypeCompatibility.IDENTICAL

    if old_n in _TEMPORAL_TYPES and new_n in _TEMPORAL_TYPES:
        # DATE -> TIMESTAMP is widening; TIMESTAMP -> DATE drops time.
        if old_n == "DATE" and new_n in {"TIMESTAMP", "TIMESTAMPTZ"}:
            return TypeCompatibility.WIDENING
        if old_n in {"TIMESTAMP", "TIMESTAMPTZ"} and new_n == "DATE":
            return TypeCompatibility.NARROWING
        return TypeCompatibility.IDENTICAL

    return TypeCompatibility.INCOMPATIBLE


# Polars dtype -> DuckDB type. Kept as instances because Polars dtypes are class-based.
_POLARS_TO_DUCKDB: dict[type, str] = {
    pl.Int8: "TINYINT",
    pl.Int16: "SMALLINT",
    pl.Int32: "INTEGER",
    pl.Int64: "BIGINT",
    pl.UInt8: "USMALLINT",
    pl.UInt16: "UINTEGER",
    pl.UInt32: "UBIGINT",
    pl.UInt64: "UBIGINT",
    pl.Float32: "FLOAT",
    pl.Float64: "DOUBLE",
    pl.Utf8: "VARCHAR",
    pl.String: "VARCHAR",
    pl.Boolean: "BOOLEAN",
    pl.Date: "DATE",
    pl.Datetime: "TIMESTAMP",
    pl.Time: "TIME",
}


def polars_to_duckdb(dtype) -> str:
    """Map a Polars dtype to a DuckDB SQL type string."""
    base = type(dtype) if not isinstance(dtype, type) else dtype
    return _POLARS_TO_DUCKDB.get(base, "VARCHAR")
