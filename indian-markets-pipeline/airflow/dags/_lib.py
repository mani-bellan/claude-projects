"""Shared imports + factory for DAG tasks.

Imports are kept inside functions where it matters so the Airflow scheduler's
DAG-parsing pass stays cheap. This module itself only declares the helper.
"""

from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def open_loader():
    """Yield a (conn, loader) pair using the configured paths."""
    from markets_pipeline.config import CONFIG
    from markets_pipeline.duckdb_client import connect
    from markets_pipeline.loaders import DuckDBLoader
    from markets_pipeline.schema import SchemaEvolution, SchemaRegistry

    with connect(CONFIG.duckdb_path) as conn:
        registry = SchemaRegistry(CONFIG.schema_registry_path)
        loader = DuckDBLoader(conn, SchemaEvolution(conn, registry))
        yield conn, loader
