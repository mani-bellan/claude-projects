"""REST API over the semantic model (FastAPI).

    GET  /health               liveness, no auth
    GET  /catalog              metrics, fields, relationships, limits
    POST /query                run a query (JSON body); add ?format=csv for CSV
    GET  /query                the same via URL parameters, for tools that import CSV by URL
    POST /sql                  compile only; returns the SQL

Errors are JSON ``{"error": "..."}``: 400 for a query the caller can fix, 401 for a bad key.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal, Sequence

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .auth import ApiKeyMiddleware
from .errors import QueryError
from .service import SemanticService, to_csv

log = logging.getLogger("ossie_duck.rest")

Name = Annotated[str, Field(min_length=1, max_length=200)]
FilterText = Annotated[str, Field(min_length=1, max_length=500)]


class OrderBy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    by: Name
    direction: Literal["asc", "desc"] = "asc"


class QueryBody(BaseModel):
    """A semantic query. Names come from ``GET /catalog``."""

    model_config = ConfigDict(extra="forbid")

    metrics: Annotated[list[Name], Field(min_length=1, max_length=50)]
    dimensions: Annotated[list[Name], Field(max_length=50)] = []
    filters: Annotated[list[FilterText], Field(max_length=20)] = []
    order_by: Annotated[list[OrderBy | Name], Field(max_length=20)] = []
    limit: Annotated[int | None, Field(ge=1)] = None
    include_sql: bool = False

    def as_payload(self) -> dict:
        data = self.model_dump(exclude={"include_sql"})
        data["order_by"] = [o if isinstance(o, str) else {"by": o["by"], "direction": o["direction"]} for o in data["order_by"]]
        return data


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def create_app(
    service: SemanticService,
    api_keys: Sequence[str] = (),
    cors_origins: Sequence[str] = (),
) -> FastAPI:
    app = FastAPI(
        title=f"ossie-duck: {service.model.name}",
        description=service.model.description or "Semantic query API",
        version=__version__,
    )

    @app.exception_handler(QueryError)
    async def _query_error(_: Request, exc: QueryError) -> JSONResponse:
        return _error(400, str(exc))

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"] if p not in ("body", "query"))
        return _error(400, f"invalid request{' (' + where + ')' if where else ''}: {first['msg']}")

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return _error(500, "internal error")

    def respond(result: dict, fmt: str) -> Response:
        if fmt == "csv":
            return Response(
                to_csv(result["columns"], result["rows"]),
                media_type="text/csv; charset=utf-8",
                headers={"X-Row-Count": str(result["row_count"]), "X-Truncated": str(result["truncated"]).lower()},
            )
        return JSONResponse(result)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": service.model.name}

    @app.get("/catalog")
    def catalog() -> dict:
        return service.catalog()

    @app.post("/query")
    def query_post(body: QueryBody, format: Literal["json", "csv"] = "json") -> Response:
        return respond(service.query(body.as_payload(), include_sql=body.include_sql), format)

    @app.get("/query")
    def query_get(
        metric: Annotated[list[Name], Query(min_length=1, max_length=50)],
        dimension: Annotated[list[Name], Query(max_length=50)] = [],
        filter: Annotated[list[FilterText], Query(max_length=20)] = [],
        order: Annotated[list[Name], Query(description="column or column:desc", max_length=20)] = [],
        limit: Annotated[int | None, Query(ge=1)] = None,
        format: Literal["json", "csv"] = "json",
        include_sql: bool = False,
    ) -> Response:
        payload = {"metrics": metric, "dimensions": dimension, "filters": filter, "order_by": order, "limit": limit}
        return respond(service.query(payload, include_sql=include_sql), format)

    @app.post("/sql")
    def sql(body: QueryBody) -> dict:
        return service.explain(body.as_payload())

    # Middleware order: the last one added is the outermost. CORS must wrap auth so that
    # browser preflight (OPTIONS) requests, which carry no key, are answered.
    if api_keys:
        app.add_middleware(ApiKeyMiddleware, keys=list(api_keys))
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "X-API-Key", "Content-Type"],
            allow_credentials=False,
        )
    return app
