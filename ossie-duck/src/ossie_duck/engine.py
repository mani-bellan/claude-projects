"""Run compiled semantic queries on DuckDB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from .compiler import CompiledQuery, QueryRequest, compile_query, _source_sql
from .errors import QueryError
from .model import SemanticModel


@dataclass
class QueryResult:
    compiled: CompiledQuery
    columns: list[str]
    rows: list[tuple[Any, ...]]

    @property
    def sql(self) -> str:
        return self.compiled.sql

    @property
    def warnings(self) -> list[str]:
        return self.compiled.warnings

    def to_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


class Engine:
    """Bind a semantic model to a DuckDB connection.

    ``rebind`` maps source prefixes in the model to the names they have in your
    database, e.g. ``{"tpcds.public": "main"}`` makes ``tpcds.public.store_sales``
    resolve to ``main.store_sales``.
    """

    def __init__(
        self,
        model: SemanticModel,
        con: duckdb.DuckDBPyConnection | None = None,
        rebind: dict[str, str] | None = None,
    ):
        self.model = model
        self.con = con if con is not None else duckdb.connect()
        self.rebind = dict(rebind or {})

    def _rebind_hint(self, exc: Exception) -> str:
        """When a table is missing, tell the reader how the model names its tables and how to map them."""
        if "Catalog Error" not in str(exc):
            return ""
        named = [ds.source for ds in self.model.datasets.values() if "." in ds.source and " " not in ds.source.strip()]
        if not named:
            return ""
        prefix = named[0].rpartition(".")[0]
        return (
            f"\n\nHint: the model names its tables like {named[0]!r}. If your database calls them something "
            f"else, map them with --rebind (for example --rebind {prefix}=main)."
        )

    def compile(self, request: QueryRequest) -> CompiledQuery:
        return compile_query(self.model, request, self.rebind)

    def query(self, request: QueryRequest) -> QueryResult:
        compiled = self.compile(request)
        try:
            cursor = self.con.execute(compiled.sql)
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        except duckdb.Error as exc:
            headline = str(exc).splitlines()[0]
            raise QueryError(
                f"DuckDB rejected the generated SQL: {headline}{self._rebind_hint(exc)}\n\nGenerated SQL:\n{compiled.sql}"
            ) from exc
        return QueryResult(compiled, columns, rows)

    def check_sources(self) -> list[str]:
        """Return a message for every dataset whose source cannot be read."""
        problems = []
        for ds in self.model.datasets.values():
            try:
                source = _source_sql(ds.source, self.rebind)
                self.con.execute(f"SELECT * FROM {source} LIMIT 0")
            except (duckdb.Error, QueryError) as exc:
                problems.append(f"dataset {ds.name}: {str(exc).splitlines()[0]}{self._rebind_hint(exc)}")
        return problems
