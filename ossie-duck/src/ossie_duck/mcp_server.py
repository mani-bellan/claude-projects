"""MCP server over the semantic model, so AI agents can ask business questions.

Tools (all read-only):

* ``describe_model``  - the catalog: metrics, fields, relationships, limits.
* ``semantic_query``  - run a query by naming metrics, dimensions and filters.
* ``explain_query``   - compile only; returns the SQL.

Resource: ``ossie://catalog`` (the same catalog as JSON).

The agent never writes SQL; it picks names from the model, and the compiler builds
the query. Transports: stdio (an MCP client launches this process) or streamable HTTP
(optionally behind the same API-key middleware as the REST API).

Written against the ``mcp`` 2.x SDK (``MCPServer``; in 1.x this class was ``FastMCP``).
"""

from __future__ import annotations

import functools
import json
from typing import Any, Callable, Sequence

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .auth import ApiKeyMiddleware
from .errors import QueryError
from .service import SemanticService

_READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

_USAGE = (
    "Call describe_model first to see the available metrics and fields. Then call semantic_query "
    "with metric names (metrics), fields to group by written dataset.field (dimensions), and optional "
    "filters such as \"store.s_state = 'CA'\". Use only names from the catalog; never write SQL. "
    "Window metrics (running totals, ranks, period-over-period changes) need the grouping their "
    "description asks for."
)


def _expected_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Report ``QueryError`` (an unknown name, a rejected filter, a timeout) to the agent.

    The SDK shows the model the message of a ``ToolError`` and hides the text of any other exception
    as a crash. A ``QueryError`` is something the agent can fix by trying again ("Did you mean:
    total_sales?"), so it becomes a ``ToolError``; genuine bugs stay hidden and are logged.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except QueryError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def create_mcp_server(service: SemanticService, name: str | None = None) -> MCPServer:
    model = service.model
    instructions = _USAGE
    if model.ai_instructions:
        instructions += f"\n\nFrom the model's author: {model.ai_instructions}"

    server = MCPServer(name or f"ossie-duck: {model.name}", instructions=instructions)

    @server.tool(
        description=(
            "Describe the semantic model: every metric (with description and synonyms), every field you can "
            "group or filter by (dataset.field, with type and whether it is a time field), the relationships "
            "between datasets, and the row limit. Call this before querying."
        ),
        annotations=_READ_ONLY,
    )
    @_expected_errors
    def describe_model() -> dict[str, Any]:
        return service.catalog()

    @server.tool(
        description=(
            "Answer an analytics question by computing metrics grouped by dimensions. "
            "`metrics`: metric names as listed by describe_model (e.g. total_sales or store_sales.total_quantity). "
            "`dimensions`: fields to group by, written dataset.field. "
            "`filters`: conditions over dataset.field using comparisons, IN, BETWEEN, LIKE, IS NULL, AND/OR/NOT and "
            "literals, e.g. \"store.s_state = 'CA'\" or \"date_dim.d_year >= 2023\". "
            "`order_by`: selected metric/dimension names, optionally with ':desc', e.g. \"total_sales:desc\". "
            "Returns columns and rows, a truncated flag, and warnings (read the warnings: some metrics can be "
            "overcounted when grouped by fields of another dataset). Set include_sql to see the generated SQL."
        ),
        annotations=_READ_ONLY,
    )
    @_expected_errors
    def semantic_query(
        metrics: list[str],
        dimensions: list[str] | None = None,
        filters: list[str] | None = None,
        order_by: list[str] | None = None,
        limit: int | None = None,
        include_sql: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "metrics": metrics,
            "dimensions": dimensions,
            "filters": filters,
            "order_by": order_by,
            "limit": limit,
        }
        return service.query(payload, include_sql=include_sql)

    @server.tool(
        description="Compile a query to SQL without running it. Takes the same arguments as semantic_query.",
        annotations=_READ_ONLY,
    )
    @_expected_errors
    def explain_query(
        metrics: list[str],
        dimensions: list[str] | None = None,
        filters: list[str] | None = None,
        order_by: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return service.explain(
            {"metrics": metrics, "dimensions": dimensions, "filters": filters, "order_by": order_by, "limit": limit}
        )

    @server.resource(
        "ossie://catalog",
        name="catalog",
        description="The semantic model catalog as JSON",
        mime_type="application/json",
    )
    def catalog_resource() -> str:
        return json.dumps(service.catalog(), indent=2)

    @server.custom_route("/health", methods=["GET"])
    async def health(_request):  # only reachable on the HTTP transport
        from starlette.responses import JSONResponse

        return JSONResponse({"status": "ok", "model": model.name})

    return server


def create_http_app(
    service: SemanticService,
    api_keys: Sequence[str] = (),
    host: str = "127.0.0.1",
):
    """The MCP server as an ASGI app (streamable HTTP at ``/mcp``), optionally behind API-key auth."""
    app = create_mcp_server(service).streamable_http_app(host=host)
    if api_keys:
        app.add_middleware(ApiKeyMiddleware, keys=list(api_keys))
    return app
