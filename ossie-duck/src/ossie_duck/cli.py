"""Command line interface: ``ossie-duck validate | list | sql | query | ask | demo``."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

import duckdb

from .compiler import QueryRequest
from .engine import Engine, QueryResult
from .model import ModelValidationError, OssieError, SemanticModel, load_model
from .sample_data import load_synthetic_tpcds, load_tpcds_extension

DEMO_REBIND = {"tpcds.public": "main"}


def bundled_example() -> Path:
    """Path of the TPC-DS example model (packaged, or the repo checkout)."""
    here = Path(__file__).resolve()
    for candidate in (here.parent / "examples", here.parents[2] / "examples"):
        path = candidate / "tpcds_semantic_model.yaml"
        if path.is_file():
            return path
    raise OssieError("bundled example model not found; pass a model path explicitly")


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #


def _cell(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    if isinstance(value, Decimal):
        return f"{value:,}"
    return str(value)


def format_table(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    cells = [[_cell(v) for v in row] for row in rows]
    numeric = [
        all(isinstance(row[i], (int, float, Decimal)) and not isinstance(row[i], bool) for row in rows if row[i] is not None)
        and any(row[i] is not None for row in rows)
        for i in range(len(columns))
    ]
    widths = [max([len(c)] + [len(r[i]) for r in cells]) for i, c in enumerate(columns)]

    def line(values: list[str]) -> str:
        parts = [v.rjust(w) if numeric[i] else v.ljust(w) for i, (v, w) in enumerate(zip(values, widths))]
        return "  ".join(parts).rstrip()

    out = [line(columns), "  ".join("-" * w for w in widths)]
    out += [line(r) for r in cells]
    out.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return "\n".join(out)


def render(result: QueryResult, fmt: str) -> str:
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(result.columns)
        writer.writerows(result.rows)
        return buf.getvalue().rstrip("\n")
    if fmt == "json":
        return json.dumps(result.to_dicts(), default=str, indent=2)
    return format_table(result.columns, result.rows)


# --------------------------------------------------------------------------- #
# Argument handling
# --------------------------------------------------------------------------- #


def _split(values: list[str] | None) -> list[str]:
    return [part.strip() for v in (values or []) for part in v.split(",") if part.strip()]


def _request(args: argparse.Namespace) -> QueryRequest:
    order = []
    for item in args.order or []:
        key, _, direction = item.partition(":")
        order.append((key, direction or "asc"))
    return QueryRequest(
        metrics=_split(args.metric),
        dimensions=_split(args.dimension),
        filters=args.filter or [],
        order_by=order,
        limit=args.limit,
    )


def _rebind(args: argparse.Namespace) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in getattr(args, "rebind", None) or []:
        prefix, sep, target = item.partition("=")
        if not sep:
            raise OssieError(f"--rebind expects PREFIX=TARGET, got {item!r}")
        out[prefix] = target
    return out


def _engine(args: argparse.Namespace, model: SemanticModel) -> Engine:
    rebind = _rebind(args)
    if getattr(args, "demo_data", False):
        con = duckdb.connect()
        load_synthetic_tpcds(con)
        for k, v in DEMO_REBIND.items():
            rebind.setdefault(k, v)
    elif getattr(args, "db", None):
        if not Path(args.db).is_file():
            raise OssieError(f"database file not found: {args.db}")
        con = duckdb.connect(args.db, read_only=True)
    else:
        con = duckdb.connect()
    return Engine(model, con, rebind)


def _print_warnings(warnings: list[str]) -> None:
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        model = load_model(args.model)
    except ModelValidationError as exc:
        for issue in exc.issues:
            print(issue, file=sys.stderr)
        print(f"{args.model}: INVALID ({len(exc.issues)} problem(s))", file=sys.stderr)
        return 1
    for issue in model.issues:
        print(issue, file=sys.stderr)
    print(
        f"{args.model}: OK - model {model.name!r}, {len(model.datasets)} datasets, "
        f"{len(model.relationships)} relationships, {len(model.all_metrics())} metrics"
    )
    if args.db or args.demo_data or args.rebind:
        problems = _engine(args, model).check_sources()
        for p in problems:
            print(f"source: {p}", file=sys.stderr)
        if problems:
            return 1
        print("all dataset sources are readable")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    print(f"{model.name}" + (f" - {model.description}" if model.description else ""))
    print("\nMetrics")
    for m in model.all_metrics():
        syn = f"  [{', '.join(m.synonyms)}]" if m.synonyms else ""
        print(f"  {m.ref:<32} {m.datatype or '':<9} {m.description}{syn}")
    print("\nFields (use as dimensions and in filters)")
    for ds in model.datasets.values():
        print(f"  {ds.name}  <- {ds.source}")
        for f in ds.fields.values():
            tags = ",".join(t for t in (f.datatype, "time" if f.is_time else None) if t)
            print(f"    {ds.name + '.' + f.name:<34} {tags:<14} {f.description}")
    print("\nRelationships (many -> one)")
    for r in model.relationships:
        on = ", ".join(f"{a} = {b}" for a, b in zip(r.from_columns, r.to_columns))
        print(f"  {r.name}: {r.from_dataset} -> {r.to_dataset} on {on}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    from . import graph as g

    model = load_model(args.model)
    graph = g.build_graph(model)
    fmt = args.format
    if fmt is None:
        suffix = Path(args.output).suffix.lower() if args.output else ""
        fmt = {".html": "html", ".htm": "html", ".json": "json"}.get(suffix, "mermaid")
    if fmt == "html":
        text = g.to_html(graph, title=args.title)
    elif fmt == "json":
        text = g.to_json(graph)
    else:
        text = g.to_mermaid(graph, fields=args.fields, synonyms=not args.no_synonyms)
        if args.output and Path(args.output).suffix.lower() == ".md":
            text = f"```mermaid\n{text}```\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output} ({fmt})", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def cmd_sql(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    compiled = Engine(model, rebind=_rebind(args)).compile(_request(args))
    print(compiled.sql)
    _print_warnings(compiled.warnings)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    result = _engine(args, model).query(_request(args))
    if args.show_sql:
        print(result.sql + "\n")
    print(render(result, args.format))
    _print_warnings(result.warnings)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from .ask import ask

    model = load_model(args.model)
    answer = ask(_engine(args, model), args.question)
    req = answer.request
    print(
        f"metrics={req.metrics} dimensions={req.dimensions} filters={req.filters} "
        f"order_by={req.order_by} limit={req.limit}\n"
    )
    if args.show_sql:
        print(answer.result.sql + "\n")
    print(render(answer.result, args.format))
    _print_warnings(answer.result.warnings)
    return 0


def _build_service(args: argparse.Namespace):
    """Build the shared SemanticService used by ``serve`` and ``mcp``."""
    from .service import SemanticService

    model = load_model(args.model)
    for issue in model.issues:  # stderr only: stdout belongs to the protocol on MCP stdio
        print(issue, file=sys.stderr)
    engine = _engine(args, model)
    return SemanticService(
        model,
        engine.con,
        engine.rebind,
        max_rows=args.max_rows,
        timeout_s=args.timeout,
        base_filters=args.base_filter or (),
    )


def _keys_for(host: str) -> list[str]:
    """API keys from the environment; refuse to listen on a network address without any."""
    from .auth import ENV_VAR, is_loopback, keys_from_env

    keys = keys_from_env()
    if not keys and not is_loopback(host):
        raise OssieError(
            f"refusing to listen on {host} without authentication. Set {ENV_VAR} to one or more keys "
            "(comma-separated, at least 16 characters each), or bind to 127.0.0.1."
        )
    return keys


def _need(module: str, extra: str) -> None:
    try:
        __import__(module)
    except ImportError as exc:
        raise OssieError(f"this command needs {module}: pip install 'ossie-duck[{extra}]'") from exc


def _announce(what: str, host: str, port: int, keys: list[str], service) -> None:
    auth = f"API key required ({len(keys)} configured)" if keys else "NO authentication (loopback only)"
    scope = f"; base filters: {', '.join(service.base_filters)}" if service.base_filters else ""
    print(
        f"{what} for model {service.model.name!r} on http://{host}:{port} - {auth}; "
        f"max {service.max_rows} rows, {service.timeout_s:g}s timeout{scope}",
        file=sys.stderr,
    )


def cmd_serve(args: argparse.Namespace) -> int:
    _need("fastapi", "serve")
    _need("uvicorn", "serve")
    import uvicorn

    from .rest import create_app

    keys = _keys_for(args.host)
    service = _build_service(args)
    _announce("REST API (docs at /docs)", args.host, args.port, keys, service)
    uvicorn.run(create_app(service, keys, args.cors_origin or ()), host=args.host, port=args.port, log_level="info")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    _need("mcp", "mcp")
    from .mcp_server import create_http_app, create_mcp_server

    if args.transport == "stdio":
        # The MCP client launches this process; the trust boundary is the local user, so no key.
        service = _build_service(args)
        print(f"MCP server for model {service.model.name!r} on stdio", file=sys.stderr)
        create_mcp_server(service).run("stdio")
        return 0

    _need("uvicorn", "serve")
    import uvicorn

    keys = _keys_for(args.host)
    service = _build_service(args)
    _announce("MCP server (streamable HTTP at /mcp)", args.host, args.port, keys, service)
    uvicorn.run(create_http_app(service, keys, args.host), host=args.host, port=args.port, log_level="info")
    return 0


DEMO_QUERIES = [
    ("Sales and profit by year", QueryRequest(metrics=["total_sales", "total_profit"], dimensions=["date_dim.d_year"])),
    (
        "Top 5 brands by sales in California",
        QueryRequest(
            metrics=["total_sales"],
            dimensions=["item.i_brand"],
            filters=["store.s_state = 'CA'"],
            order_by=[("total_sales", "desc")],
            limit=5,
        ),
    ),
    (
        "Month-over-month sales change, 2023",
        QueryRequest(
            metrics=["total_sales", "monthly_sales_change"],
            dimensions=["date_dim.d_year", "date_dim.d_moy"],
            filters=["date_dim.d_year = 2023"],
            limit=6,
        ),
    ),
]


def cmd_demo(args: argparse.Namespace) -> int:
    model = load_model(args.model or bundled_example())
    if args.tpcds_extension:
        con = duckdb.connect()
        load_tpcds_extension(con, args.scale)
        engine = Engine(model, con, DEMO_REBIND)
    else:
        engine = _engine(argparse.Namespace(demo_data=True, db=None, rebind=None), model)
    for title, request in DEMO_QUERIES:
        result = engine.query(request)
        print(f"== {title}")
        if args.show_sql:
            print(result.sql + "\n")
        print(render(result, "table") + "\n")
    return 0


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def _add_data_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", help="DuckDB database file holding the tables (opened read-only)")
    p.add_argument("--demo-data", action="store_true", help="use built-in synthetic TPC-DS tables (offline)")
    p.add_argument("--rebind", action="append", metavar="PREFIX=TARGET", help="map a source prefix to your database, e.g. tpcds.public=main")


def _add_query_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-m", "--metric", action="append", help="metric to compute (repeatable, or comma-separated)")
    p.add_argument("-d", "--dimension", action="append", help="dataset.field to group by (repeatable)")
    p.add_argument("-f", "--filter", action="append", help="filter, e.g. \"store.s_state = 'CA'\" (repeatable)")
    p.add_argument("--order", action="append", metavar="COLUMN[:asc|:desc]", help="order by a selected output")
    p.add_argument("--limit", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ossie-duck",
        description="Compile Apache Ossie semantic models (spec 0.2.0.dev0) to SQL and run them on DuckDB.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate a model file (and optionally that its sources exist)")
    p.add_argument("model")
    _add_data_args(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("list", help="list the metrics, fields and relationships of a model")
    p.add_argument("model")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("graph", help="draw the model as a graph: Mermaid, interactive HTML or JSON")
    p.add_argument("model")
    p.add_argument("-o", "--output", metavar="FILE", help="write to FILE instead of printing (the extension picks the format: .html, .json, .md/.mmd)")
    p.add_argument("--format", choices=["mermaid", "html", "json"], help="default: from the -o extension, else mermaid")
    p.add_argument("--fields", action="store_true", help="Mermaid only: also draw every field (best for small models; the HTML page has a toggle)")
    p.add_argument("--no-synonyms", action="store_true", help="Mermaid only: leave out the synonyms")
    p.add_argument("--title", help="HTML only: page title")
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser("sql", help="print the SQL for a query without running it")
    p.add_argument("model")
    _add_query_args(p)
    p.add_argument("--rebind", action="append", metavar="PREFIX=TARGET")
    p.set_defaults(func=cmd_sql)

    p = sub.add_parser("query", help="run a query")
    p.add_argument("model")
    _add_query_args(p)
    _add_data_args(p)
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.add_argument("--show-sql", action="store_true")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("ask", help="answer a plain-English question (needs the [ai] extra and ANTHROPIC_API_KEY)")
    p.add_argument("model")
    p.add_argument("question")
    _add_data_args(p)
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.add_argument("--show-sql", action="store_true")
    p.set_defaults(func=cmd_ask)

    def add_service_args(p: argparse.ArgumentParser) -> None:
        from .service import DEFAULT_MAX_ROWS, DEFAULT_TIMEOUT_S

        p.add_argument("model")
        _add_data_args(p)
        p.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS, help="cap on rows returned per query (default %(default)s)")
        p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="cancel queries after this many seconds (default %(default)s)")
        p.add_argument(
            "--base-filter", action="append", metavar="FILTER",
            help="condition ANDed onto every query, e.g. \"store.s_state = 'CA'\" (repeatable)",
        )

    p = sub.add_parser(
        "serve",
        help="serve the model over REST (needs the [serve] extra; keys come from OSSIE_DUCK_API_KEYS)",
    )
    add_service_args(p)
    p.add_argument("--host", default="127.0.0.1", help="default 127.0.0.1; other addresses require API keys")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--cors-origin", action="append", metavar="ORIGIN", help="allow browser requests from this origin (repeatable)")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("mcp", help="serve the model to AI agents over MCP (needs the [mcp] extra)")
    add_service_args(p)
    p.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    p.add_argument("--host", default="127.0.0.1", help="http transport only")
    p.add_argument("--port", type=int, default=8001, help="http transport only")
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("demo", help="run sample queries on the bundled TPC-DS model with synthetic data")
    p.add_argument("model", nargs="?", help="defaults to the bundled TPC-DS example")
    p.add_argument("--show-sql", action="store_true")
    p.add_argument("--tpcds-extension", action="store_true", help="use DuckDB's tpcds extension instead (needs network once)")
    p.add_argument("--scale", type=float, default=0.01, help="TPC-DS scale factor with --tpcds-extension")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ModelValidationError as exc:
        for issue in exc.issues:
            print(issue, file=sys.stderr)
        return 1
    except OssieError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except duckdb.Error as exc:  # e.g. a file that is not a DuckDB database
        print(f"error: {str(exc).splitlines()[0]}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
