"""Transport-neutral service layer shared by the REST API and the MCP server.

Everything a remote consumer can do goes through :class:`SemanticService`, so the
two adapters cannot drift apart on what a metric means or what a caller may do.

Guardrails applied to every request:

* **Row cap** (``max_rows``): at most this many rows are returned; ``truncated`` says
  whether there were more.
* **Timeout** (``timeout_s``): a running query is interrupted after this many seconds.
* **Base filters**: conditions that are ANDed onto *every* query, for example
  ``store.s_state = 'CA'``. They are validated when the service starts.
* Queries are only ever built by the compiler from metric and field names; callers
  cannot send SQL.
"""

from __future__ import annotations

import datetime as dt
import threading
from decimal import Decimal
from typing import Any, Mapping, Sequence

import duckdb

from .compiler import QueryRequest, compile_query, validate_filter
from .errors import QueryError
from .model import SemanticModel

DEFAULT_MAX_ROWS = 1000
DEFAULT_TIMEOUT_S = 30.0


def json_value(value: Any) -> Any:
    """Convert a DuckDB value to something ``json.dumps`` accepts.

    ``Decimal`` becomes ``float`` (JSON has one number type, so very large or very precise
    decimals can lose precision); dates and times become ISO-8601 strings; anything
    unusual becomes its ``str``.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    return str(value)


class SemanticService:
    """Catalog and query access to one semantic model on one DuckDB database."""

    def __init__(
        self,
        model: SemanticModel,
        con: duckdb.DuckDBPyConnection,
        rebind: Mapping[str, str] | None = None,
        *,
        max_rows: int = DEFAULT_MAX_ROWS,
        timeout_s: float | None = DEFAULT_TIMEOUT_S,
        base_filters: Sequence[str] = (),
    ):
        if max_rows < 1:
            raise ValueError("max_rows must be at least 1")
        if timeout_s is not None and timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        for text in base_filters:
            validate_filter(model, text)  # fail at startup, not on the first request
        self.model = model
        self.con = con
        self.rebind = dict(rebind or {})
        self.max_rows = max_rows
        self.timeout_s = timeout_s
        self.base_filters = tuple(base_filters)

    # ------------------------------------------------------------------ catalog

    def catalog(self) -> dict[str, Any]:
        """Everything a consumer needs to *write* a query: names, types, descriptions, synonyms.

        Physical table names (``source``) are deliberately left out.
        """
        m = self.model
        return {
            "name": m.name,
            "description": m.description,
            "instructions": m.ai_instructions,
            "spec_version": m.version,
            "limits": {"max_rows": self.max_rows, "timeout_s": self.timeout_s},
            "metrics": [
                {
                    "ref": x.ref,
                    "name": x.name,
                    "scope": "dataset" if x.dataset else "model",
                    "dataset": x.dataset,
                    "datatype": x.datatype,
                    "description": x.description,
                    "synonyms": list(x.synonyms),
                }
                for x in m.all_metrics()
            ],
            "datasets": [
                {
                    "name": ds.name,
                    "description": ds.description,
                    "synonyms": list(ds.synonyms),
                    "primary_key": list(ds.primary_key),
                    "fields": [
                        {
                            "ref": f"{ds.name}.{f.name}",
                            "name": f.name,
                            "datatype": f.datatype,
                            "is_time": f.is_time,
                            "description": f.description,
                            "synonyms": list(f.synonyms),
                        }
                        for f in ds.fields.values()
                    ],
                }
                for ds in m.datasets.values()
            ],
            "relationships": [
                {
                    "name": r.name,
                    "from": r.from_dataset,
                    "to": r.to_dataset,
                    "from_columns": list(r.from_columns),
                    "to_columns": list(r.to_columns),
                }
                for r in m.relationships
            ],
        }

    # ------------------------------------------------------------------ queries

    def _request(self, payload: QueryRequest | Mapping[str, Any]) -> QueryRequest:
        request = payload if isinstance(payload, QueryRequest) else QueryRequest.from_dict(dict(payload))
        if self.base_filters:
            request = QueryRequest(
                metrics=request.metrics,
                dimensions=request.dimensions,
                filters=[*request.filters, *self.base_filters],
                order_by=request.order_by,
                limit=request.limit,
            )
        return request

    def explain(self, payload: QueryRequest | Mapping[str, Any]) -> dict[str, Any]:
        """Compile without running. Base filters are included in the SQL."""
        compiled = compile_query(self.model, self._request(payload), self.rebind)
        return {
            "sql": compiled.sql,
            "columns": compiled.columns,
            "root_dataset": compiled.root,
            "datasets": compiled.datasets,
            "warnings": compiled.warnings,
        }

    def query(self, payload: QueryRequest | Mapping[str, Any], *, include_sql: bool = False) -> dict[str, Any]:
        """Compile and run a query, returning JSON-safe rows.

        Raises :class:`QueryError` for anything the caller can fix (unknown names, bad filter,
        timeout, DuckDB rejecting the SQL). The error text never contains the generated SQL.
        """
        compiled = compile_query(self.model, self._request(payload), self.rebind)

        cursor = self.con.cursor()  # one cursor per request: safe to use from several threads
        timer: threading.Timer | None = None
        timed_out = threading.Event()
        if self.timeout_s is not None:
            def _stop() -> None:
                timed_out.set()
                cursor.interrupt()

            timer = threading.Timer(self.timeout_s, _stop)
            timer.daemon = True
            timer.start()
        try:
            cursor.execute(compiled.sql)
            columns = [d[0] for d in cursor.description]
            fetched = cursor.fetchmany(self.max_rows + 1)
        except duckdb.Error as exc:
            if timed_out.is_set():
                raise QueryError(f"the query ran longer than the {self.timeout_s:g}s limit and was cancelled") from exc
            raise QueryError(f"the database rejected the query: {str(exc).splitlines()[0][:300]}") from exc
        finally:
            if timer is not None:
                timer.cancel()
            cursor.close()

        truncated = len(fetched) > self.max_rows
        rows = [[json_value(v) for v in row] for row in fetched[: self.max_rows]]
        result: dict[str, Any] = {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "max_rows": self.max_rows,
            "warnings": list(compiled.warnings),
        }
        if truncated:
            result["warnings"].append(
                f"the result was cut off at {self.max_rows} rows; add filters or a limit to see the rest"
            )
        if include_sql:
            result["sql"] = compiled.sql
        return result


# --------------------------------------------------------------------------- #
# CSV (for spreadsheets and BI tools that import by URL)
# --------------------------------------------------------------------------- #

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def to_csv(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render rows as CSV.

    Text cells that a spreadsheet would run as a formula (leading ``=``, ``+``, ``-``, ``@``) are
    prefixed with an apostrophe, because dimension values come from the database and may be
    attacker-controlled. Numbers are left alone.
    """
    import csv
    import io

    def safe(value: Any) -> Any:
        if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
            return "'" + value
        return "" if value is None else value

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([safe(c) for c in columns])
    for row in rows:
        writer.writerow([safe(v) for v in row])
    return buf.getvalue()
