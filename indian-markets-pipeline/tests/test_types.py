"""Tests for type-compatibility classification."""

from __future__ import annotations

import polars as pl

from markets_pipeline.schema.types import (
    TypeCompatibility,
    compare_types,
    normalize_type,
    polars_to_duckdb,
)


class TestNormalize:
    def test_strips_parameters(self):
        assert normalize_type("VARCHAR(50)") == "VARCHAR"
        assert normalize_type("DECIMAL(10, 2)") == "DECIMAL"

    def test_applies_aliases(self):
        assert normalize_type("INT") == "INTEGER"
        assert normalize_type("DOUBLE PRECISION") == "DOUBLE"
        assert normalize_type("REAL") == "FLOAT"

    def test_case_insensitive(self):
        assert normalize_type("varchar") == "VARCHAR"


class TestCompareTypes:
    def test_identical(self):
        assert compare_types("INTEGER", "INTEGER") is TypeCompatibility.IDENTICAL

    def test_widening_int_to_bigint(self):
        assert compare_types("INTEGER", "BIGINT") is TypeCompatibility.WIDENING

    def test_widening_int_to_double(self):
        assert compare_types("INTEGER", "DOUBLE") is TypeCompatibility.WIDENING

    def test_narrowing_bigint_to_int(self):
        assert compare_types("BIGINT", "INTEGER") is TypeCompatibility.NARROWING

    def test_narrowing_double_to_int(self):
        assert compare_types("DOUBLE", "INTEGER") is TypeCompatibility.NARROWING

    def test_incompatible_families(self):
        assert compare_types("INTEGER", "VARCHAR") is TypeCompatibility.INCOMPATIBLE
        assert compare_types("DATE", "INTEGER") is TypeCompatibility.INCOMPATIBLE

    def test_string_family_treats_subtypes_identical(self):
        assert compare_types("VARCHAR", "TEXT") is TypeCompatibility.IDENTICAL
        assert compare_types("VARCHAR(10)", "VARCHAR(50)") is TypeCompatibility.IDENTICAL

    def test_date_to_timestamp_widens(self):
        assert compare_types("DATE", "TIMESTAMP") is TypeCompatibility.WIDENING
        assert compare_types("TIMESTAMP", "DATE") is TypeCompatibility.NARROWING


class TestPolarsToDuckDB:
    def test_int64(self):
        assert polars_to_duckdb(pl.Int64) == "BIGINT"

    def test_float64(self):
        assert polars_to_duckdb(pl.Float64) == "DOUBLE"

    def test_string(self):
        assert polars_to_duckdb(pl.Utf8) == "VARCHAR"

    def test_date(self):
        assert polars_to_duckdb(pl.Date) == "DATE"

    def test_unknown_falls_back_to_varchar(self):
        class Mystery:
            pass

        assert polars_to_duckdb(Mystery) == "VARCHAR"
