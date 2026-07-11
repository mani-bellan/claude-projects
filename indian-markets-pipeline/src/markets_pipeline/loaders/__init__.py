"""DuckDB loaders. Schema-aware, idempotent."""

from .duckdb_loader import DuckDBLoader, LoadResult

__all__ = ["DuckDBLoader", "LoadResult"]
