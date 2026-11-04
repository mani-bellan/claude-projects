"""Compile a semantic query into DuckDB SQL.

Approach
--------
The spec says a dataset's declared *fields* are its public interface, and that
metrics only ever reference fields. So each dataset used by a query becomes a
CTE that projects its fields (named after the field) from its ``source``::

    WITH "__store_sales" AS (SELECT ss_ext_sales_price AS "ss_ext_sales_price", ... FROM ...)

Metric expressions such as ``SUM(store_sales.ss_ext_sales_price)`` then run
unchanged against the joined CTEs, aliased by dataset name.

Joins follow the model's relationships (many-to-one, ``from`` -> ``to``) starting
from a single "root" dataset that can reach every dataset the query touches.
Rooting at the many side means joins never multiply rows.

Not supported (raises ``QueryError``): queries spanning several fact datasets,
and ambiguous join paths (two relationships between the same pair of datasets).
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field

from sqlglot import exp
from sqlglot.errors import SqlglotError

from .errors import QueryError
from .model import Metric, Relationship, SemanticModel, parse_sql, suggest


@dataclass
class QueryRequest:
    metrics: list[str]
    dimensions: list[str] = field(default_factory=list)
    #: Boolean SQL expressions over ``dataset.field`` references.
    filters: list[str] = field(default_factory=list)
    #: ``(output column or reference, "asc" | "desc")``
    order_by: list[tuple[str, str]] = field(default_factory=list)
    limit: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "QueryRequest":
        """Build a request from untrusted JSON-like input (REST body, MCP arguments, LLM tool call).

        ``order_by`` items may be ``{"by": col, "direction": "asc|desc"}`` or ``"col"`` / ``"col:desc"``.
        Raises ``QueryError`` for anything malformed.
        """
        if not isinstance(data, dict):
            raise QueryError("the query must be a JSON object")
        known = {"metrics", "dimensions", "filters", "order_by", "limit"}
        extra = sorted(set(data) - known)
        if extra:
            raise QueryError(f"unknown query field(s): {', '.join(extra)}. Allowed: {', '.join(sorted(known))}")

        def strings(key: str) -> list[str]:
            value = data.get(key) or []
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise QueryError(f"`{key}` must be a list of strings")
            return value

        order_by: list[tuple[str, str]] = []
        for item in data.get("order_by") or []:
            if isinstance(item, str):
                key, _, direction = item.partition(":")
                order_by.append((key.strip(), direction.strip() or "asc"))
            elif isinstance(item, dict) and isinstance(item.get("by"), str):
                order_by.append((item["by"], str(item.get("direction") or "asc")))
            else:
                raise QueryError("`order_by` items must be {\"by\": ..., \"direction\": ...} or \"column[:asc|desc]\"")

        limit = data.get("limit")
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool)):
            raise QueryError("`limit` must be an integer")
        return cls(
            metrics=strings("metrics"),
            dimensions=strings("dimensions"),
            filters=strings("filters"),
            order_by=order_by,
            limit=limit,
        )


@dataclass
class CompiledQuery:
    sql: str
    columns: list[str]
    root: str
    datasets: list[str]
    warnings: list[str] = field(default_factory=list)


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# Only these node types may appear in a filter. This is what stops a filter
# string (for example one proposed by an LLM) from smuggling in subqueries or
# arbitrary function calls.
_SAFE_FILTER_NODES = (
    exp.Column, exp.Identifier, exp.Literal, exp.Null, exp.Boolean, exp.Paren,
    exp.Not, exp.And, exp.Or, exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE,
    exp.In, exp.Between, exp.Like, exp.ILike, exp.Is, exp.Neg, exp.Add, exp.Sub,
    exp.Mul, exp.Div, exp.Tuple, exp.Cast, exp.DataType, exp.Lower, exp.Upper,
)


def _source_sql(source: str, rebind: dict[str, str]) -> str:
    text = source.strip()
    if re.match(r"(?is)^(select|with)\b", text):
        return f"({text})"
    if not re.fullmatch(r"[A-Za-z_][\w$]*(\.[A-Za-z_][\w$]*)*", text):
        raise QueryError(f"unsupported dataset source {source!r}: expected [db.][schema.]table or a SELECT query")
    for prefix in sorted(rebind, key=len, reverse=True):
        if text == prefix or text.startswith(prefix + "."):
            text = (rebind[prefix] + text[len(prefix):]).lstrip(".")
            break
    return ".".join(_q(part) for part in text.split("."))


def _field_expr_sql(model: SemanticModel, ds_name: str, field_name: str) -> str:
    f = model.datasets[ds_name].fields[field_name]
    if f.expression is None:
        raise QueryError(f"field {ds_name}.{field_name} has no expression this engine can run")
    try:
        return parse_sql(f.expression).sql(dialect="duckdb")
    except SqlglotError as exc:
        raise QueryError(f"field {ds_name}.{field_name}: cannot parse expression: {exc}") from exc


def _prepare_metric(model: SemanticModel, metric: Metric) -> tuple[exp.Expression, set[tuple[str, str]]]:
    """Qualify every column of a metric expression and collect (dataset, field) refs."""
    if metric.expression is None:
        raise QueryError(f"metric {metric.ref!r} has no expression this engine can run")
    try:
        tree = parse_sql(metric.expression)
    except SqlglotError as exc:
        raise QueryError(f"metric {metric.ref!r}: cannot parse expression: {exc}") from exc

    refs: set[tuple[str, str]] = set()

    def qualify(node: exp.Expression) -> exp.Expression:
        if not isinstance(node, exp.Column):
            return node
        ds_name = node.table or metric.dataset
        if not ds_name:
            raise QueryError(f"metric {metric.ref!r}: {node.name!r} must be written as dataset.field")
        if ds_name not in model.datasets or node.name not in model.datasets[ds_name].fields:
            raise QueryError(f"metric {metric.ref!r}: {ds_name}.{node.name} is not a declared field")
        refs.add((ds_name, node.name))
        return exp.column(node.name, table=ds_name, quoted=True)

    return tree.transform(qualify), refs


def _prepare_filter(model: SemanticModel, text: str) -> tuple[exp.Expression, set[tuple[str, str]]]:
    try:
        tree = parse_sql(text)
    except SqlglotError as exc:
        raise QueryError(f"cannot parse filter {text!r}: {exc}") from exc
    for node in tree.find_all(exp.Expression):
        if not isinstance(node, _SAFE_FILTER_NODES):
            raise QueryError(
                f"filter {text!r} uses {node.key.upper()}, which is not allowed. Filters may only "
                "combine dataset.field references and literals with comparison and boolean operators."
            )
    refs: set[tuple[str, str]] = set()

    def qualify(node: exp.Expression) -> exp.Expression:
        if not isinstance(node, exp.Column):
            return node
        ref = f"{node.table}.{node.name}" if node.table else node.name
        ds, f = model.resolve_field(ref)
        refs.add((ds.name, f.name))
        return exp.column(f.name, table=ds.name, quoted=True)

    return tree.transform(qualify), refs


def validate_filter(model: SemanticModel, text: str) -> None:
    """Raise ``QueryError`` unless ``text`` is an allowed filter over this model's fields."""
    _prepare_filter(model, text)


def _plan_joins(
    model: SemanticModel, needed: set[str], prefer: list[str]
) -> tuple[str, list[Relationship], list[str]]:
    """Pick a root dataset and the many-to-one joins that reach every needed dataset."""
    order = [name for name in model.datasets if name in needed]
    if len(needed) == 1:
        return order[0], [], order

    forward: dict[str, list[Relationship]] = {}
    pair_count: dict[tuple[str, str], list[str]] = {}
    for r in model.relationships:
        forward.setdefault(r.from_dataset, []).append(r)
        pair_count.setdefault((r.from_dataset, r.to_dataset), []).append(r.name)

    def reach(root: str) -> dict[str, Relationship | None]:
        parent: dict[str, Relationship | None] = {root: None}
        queue = deque([root])
        while queue:
            cur = queue.popleft()
            for r in forward.get(cur, []):
                if r.to_dataset not in parent:
                    parent[r.to_dataset] = r
                    queue.append(r.to_dataset)
        return parent

    candidates = [(name, reach(name)) for name in order]
    candidates = [(name, parent) for name, parent in candidates if needed <= set(parent)]
    if not candidates:
        raise QueryError(
            "cannot join " + ", ".join(sorted(needed)) + ": no single dataset reaches all of them through "
            "many-to-one relationships. Queries that combine several fact datasets are not supported."
        )
    root, parent = next(((n, p) for n, p in candidates if n in prefer), candidates[0])

    path_nodes: set[str] = set()
    for target in needed - {root}:
        cur = target
        while cur != root:
            path_nodes.add(cur)
            rel = parent[cur]
            names = pair_count[(rel.from_dataset, rel.to_dataset)]
            if len(names) > 1:
                raise QueryError(
                    f"ambiguous join from {rel.from_dataset!r} to {rel.to_dataset!r}: "
                    f"relationships {', '.join(names)} all connect them"
                )
            cur = rel.from_dataset
    path_nodes.add(root)
    joins = [parent[name] for name in parent if name in path_nodes and parent[name] is not None]
    used = [root] + [r.to_dataset for r in joins]
    return root, joins, used


def _fanout_warnings(metric: Metric, tree: exp.Expression, root: str) -> list[str]:
    out: list[str] = []
    for agg in tree.find_all(exp.AggFunc):
        if isinstance(agg, (exp.Min, exp.Max, exp.AnyValue)) or agg.find(exp.Distinct):
            continue
        others = {c.table for c in agg.find_all(exp.Column)} - {root}
        if others:
            out.append(
                f"metric {metric.ref!r} aggregates fields of {', '.join(sorted(others))} over the joined "
                f"{root!r} rows, so values repeat once per {root} row and may be overcounted"
            )
            break
    return out


def compile_query(
    model: SemanticModel, request: QueryRequest, rebind: dict[str, str] | None = None
) -> CompiledQuery:
    rebind = rebind or {}
    if not request.metrics:
        raise QueryError("a query needs at least one metric")
    if request.limit is not None and request.limit < 1:
        raise QueryError("limit must be a positive integer")

    # -- resolve -------------------------------------------------------------
    dims: list[tuple[str, str]] = []  # (dataset, field), de-duplicated, in order
    for ref in request.dimensions:
        ds, f = model.resolve_field(ref)
        if (ds.name, f.name) not in dims:
            dims.append((ds.name, f.name))

    metrics: list[tuple[Metric, exp.Expression]] = []
    needed_fields: set[tuple[str, str]] = set(dims)
    metric_datasets: list[str] = []
    seen_metrics: set[str] = set()
    for ref in request.metrics:
        metric = model.resolve_metric(ref)
        if metric.ref in seen_metrics:
            continue
        seen_metrics.add(metric.ref)
        tree, refs = _prepare_metric(model, metric)
        metrics.append((metric, tree))
        needed_fields |= refs
        for ds_name, _ in sorted(refs):
            if ds_name not in metric_datasets:
                metric_datasets.append(ds_name)

    filters: list[exp.Expression] = []
    for text in request.filters:
        tree, refs = _prepare_filter(model, text)
        filters.append(tree)
        needed_fields |= refs

    # -- joins ---------------------------------------------------------------
    needed = {ds for ds, _ in needed_fields}
    root, joins, used = _plan_joins(model, needed, prefer=metric_datasets)
    for r in joins:
        for col in r.from_columns:
            needed_fields.add((r.from_dataset, col))
        for col in r.to_columns:
            needed_fields.add((r.to_dataset, col))

    # -- CTEs: one per dataset, projecting only the fields the query uses ------
    ctes: list[str] = []
    for ds_name in used:
        cols = [f for d, f in sorted(needed_fields) if d == ds_name]
        # keep declaration order for readable SQL
        cols.sort(key=lambda c: list(model.datasets[ds_name].fields).index(c))
        select = ",\n      ".join(f"{_field_expr_sql(model, ds_name, c)} AS {_q(c)}" for c in cols)
        source = _source_sql(model.datasets[ds_name].source, rebind)
        ctes.append(f'  {_q("__" + ds_name)} AS (\n    SELECT\n      {select}\n    FROM {source}\n  )')

    # -- output columns ------------------------------------------------------
    taken: set[str] = set()

    def alloc(base: str, qualifier: str) -> str:
        alias = base if base not in taken else f"{qualifier}_{base}"
        n = 2
        while alias in taken:
            alias = f"{base}_{n}"
            n += 1
        taken.add(alias)
        return alias

    select_items: list[str] = []
    out_columns: list[str] = []
    lookup: dict[str, str] = {}  # any accepted spelling -> output column

    for ds_name, f_name in dims:
        alias = alloc(f_name, ds_name)
        select_items.append(f'{_q(ds_name)}.{_q(f_name)} AS {_q(alias)}')
        out_columns.append(alias)
        lookup[alias] = alias
        lookup[f"{ds_name}.{f_name}"] = alias

    warnings: list[str] = []
    for metric, tree in metrics:
        alias = alloc(metric.name, metric.dataset or "metric")
        select_items.append(f"{tree.sql(dialect='duckdb')} AS {_q(alias)}")
        out_columns.append(alias)
        lookup.setdefault(alias, alias)
        lookup[metric.ref] = alias
        warnings.extend(_fanout_warnings(metric, tree, root))

    # -- assemble ------------------------------------------------------------
    lines = ["WITH", ",\n".join(ctes), "SELECT", "  " + ",\n  ".join(select_items)]
    lines.append(f"FROM {_q('__' + root)} AS {_q(root)}")
    for r in joins:
        on = " AND ".join(
            f"{_q(r.from_dataset)}.{_q(f)} = {_q(r.to_dataset)}.{_q(t)}"
            for f, t in zip(r.from_columns, r.to_columns)
        )
        lines.append(f"LEFT JOIN {_q('__' + r.to_dataset)} AS {_q(r.to_dataset)} ON {on}")
    if filters:
        lines.append("WHERE " + "\n  AND ".join(f"({f.sql(dialect='duckdb')})" for f in filters))
    if dims:
        lines.append("GROUP BY " + ", ".join(str(i + 1) for i in range(len(dims))))

    if request.order_by:
        parts = []
        for key, direction in request.order_by:
            if key not in lookup:
                raise QueryError(
                    f"cannot order by {key!r}: it must be one of the selected outputs "
                    f"({', '.join(out_columns)})"
                    + suggest(key, list(lookup))
                )
            if direction.lower() not in ("asc", "desc"):
                raise QueryError(f"order direction must be asc or desc, got {direction!r}")
            parts.append(f"{_q(lookup[key])} {direction.upper()}")
        lines.append("ORDER BY " + ", ".join(parts))
    elif dims:
        lines.append("ORDER BY " + ", ".join(str(i + 1) for i in range(len(dims))))
    if request.limit is not None:
        lines.append(f"LIMIT {int(request.limit)}")

    return CompiledQuery(
        sql="\n".join(lines),
        columns=out_columns,
        root=root,
        datasets=used,
        warnings=warnings,
    )
