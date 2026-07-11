"""Thin DuckDB connection helper."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import duckdb


@contextmanager
def connect(path: Path | str):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    try:
        yield conn
    finally:
        conn.close()
