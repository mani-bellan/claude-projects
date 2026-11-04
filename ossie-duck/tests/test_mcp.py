"""The MCP server, driven through the real protocol by the SDK's in-process client."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp import Client

from ossie_duck.mcp_server import create_mcp_server
from ossie_duck.service import SemanticService


@pytest.fixture
def service(model, con):
    return SemanticService(model, con, {"tpcds.public": "main"})


def with_client(service, fn):
    """Run ``fn(client)`` against an in-process server and return its result."""

    async def main():
        async with Client(create_mcp_server(service)) as client:
            return await fn(client)

    return asyncio.run(main())


def test_server_advertises_tools_with_read_only_hints(service):
    tools = with_client(service, lambda c: c.list_tools()).tools
    assert {t.name for t in tools} == {"describe_model", "semantic_query", "explain_query"}
    for t in tools:
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False
    query = next(t for t in tools if t.name == "semantic_query")
    assert query.input_schema["required"] == ["metrics"]
    assert set(query.input_schema["properties"]) == {"metrics", "dimensions", "filters", "order_by", "limit", "include_sql"}


def test_instructions_carry_the_models_own_guidance(service):
    async def run(client):
        return client.instructions

    text = with_client(service, run)
    assert "describe_model" in text and "retail analytics" in text


def test_describe_model_returns_the_catalog(service):
    result = with_client(service, lambda c: c.call_tool("describe_model", {}))
    assert not result.is_error
    cat = result.structured_content
    assert cat["name"] == "tpcds_retail_model" and "total_sales" in {m["ref"] for m in cat["metrics"]}


def test_semantic_query_runs(service):
    result = with_client(
        service,
        lambda c: c.call_tool(
            "semantic_query",
            {"metrics": ["total_sales"], "dimensions": ["date_dim.d_year"], "order_by": ["d_year:desc"]},
        ),
    )
    assert not result.is_error
    out = result.structured_content
    assert out["columns"] == ["d_year", "total_sales"] and [r[0] for r in out["rows"]] == [2024, 2023]
    assert "sql" not in out


def test_semantic_query_with_filters_limit_and_sql(service):
    result = with_client(
        service,
        lambda c: c.call_tool(
            "semantic_query",
            {
                "metrics": ["total_sales"],
                "dimensions": ["item.i_category"],
                "filters": ["store.s_state = 'CA'"],
                "order_by": ["total_sales:desc"],
                "limit": 2,
                "include_sql": True,
            },
        ),
    )
    out = result.structured_content
    assert out["row_count"] == 2 and "WHERE" in out["sql"]


def test_explain_query_does_not_run(service):
    result = with_client(service, lambda c: c.call_tool("explain_query", {"metrics": ["total_sales"], "dimensions": ["item.i_brand"]}))
    out = result.structured_content
    assert out["root_dataset"] == "store_sales" and "rows" not in out and out["sql"].startswith("WITH")


def test_a_bad_name_comes_back_as_a_tool_error_the_agent_can_act_on(service):
    result = with_client(service, lambda c: c.call_tool("semantic_query", {"metrics": ["total_salez"]}))
    assert result.is_error
    text = "".join(getattr(block, "text", "") for block in result.content)
    assert "total_sales" in text  # the "did you mean" suggestion reaches the agent


def test_unsafe_filter_is_a_tool_error(service):
    result = with_client(service, lambda c: c.call_tool("semantic_query", {"metrics": ["total_sales"], "filters": ["store.s_state IN (SELECT 1)"]}))
    assert result.is_error
    assert "not allowed" in "".join(getattr(b, "text", "") for b in result.content)


def test_wrongly_typed_arguments_are_rejected_by_the_protocol_layer(service):
    result = with_client(service, lambda c: c.call_tool("semantic_query", {"metrics": "total_sales", "limit": "ten"}))
    assert result.is_error


def test_catalog_resource(service):
    async def run(client):
        listed = await client.list_resources()
        read = await client.read_resource("ossie://catalog")
        return listed, read

    listed, read = with_client(service, run)
    assert [str(r.uri) for r in listed.resources] == ["ossie://catalog"]
    cat = json.loads(read.contents[0].text)
    assert cat["name"] == "tpcds_retail_model"


def test_base_filters_apply_through_mcp(model, con):
    scoped = SemanticService(model, con, {"tpcds.public": "main"}, base_filters=["store.s_state = 'CA'"])
    result = with_client(scoped, lambda c: c.call_tool("semantic_query", {"metrics": ["total_sales"], "dimensions": ["store.s_state"]}))
    assert [r[0] for r in result.structured_content["rows"]] == ["CA"]


def test_row_cap_reaches_the_agent(model, con):
    capped = SemanticService(model, con, {"tpcds.public": "main"}, max_rows=3)
    result = with_client(capped, lambda c: c.call_tool("semantic_query", {"metrics": ["total_sales"], "dimensions": ["date_dim.d_date"]}))
    out = result.structured_content
    assert out["truncated"] is True and out["row_count"] == 3 and any("cut off" in w for w in out["warnings"])


def test_internal_crashes_do_not_leak_details_to_the_agent(service):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail /var/db/warehouse.duckdb")

    service.query = boom  # type: ignore[method-assign]
    result = with_client(service, lambda c: c.call_tool("semantic_query", {"metrics": ["total_sales"]}))
    text = "".join(getattr(b, "text", "") for b in result.content)
    assert result.is_error and "secret" not in text and "warehouse" not in text
