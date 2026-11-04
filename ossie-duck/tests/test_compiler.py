"""Compiler behaviour that does not need a database."""

from __future__ import annotations

import pytest

from ossie_duck import QueryError, QueryRequest, compile_query, parse_model


def compile_(doc, request, rebind=None):
    return compile_query(parse_model(doc), request, rebind)


def test_single_dataset_needs_no_join(doc):
    q = compile_(doc, QueryRequest(metrics=["orders.total"]))
    assert "JOIN" not in q.sql and "GROUP BY" not in q.sql
    assert q.columns == ["total"] and q.root == "orders" and q.datasets == ["orders"]


def test_joins_follow_relationships_from_the_many_side(doc):
    q = compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["customers.region"]))
    assert q.root == "orders" and q.datasets == ["orders", "customers"]
    assert 'LEFT JOIN "__customers" AS "customers" ON "orders"."cust" = "customers"."id"' in q.sql
    assert "GROUP BY 1" in q.sql and "ORDER BY 1" in q.sql


def test_ctes_project_only_the_fields_the_query_uses(doc):
    q = compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["customers.region"]))
    assert "score" not in q.sql  # never referenced


def test_composite_keys_are_anded(doc):
    doc["datasets"][0]["fields"].append({"name": "ver", "expression": {"sql": "ver"}})
    doc["datasets"][1]["fields"].append({"name": "ver", "expression": {"sql": "ver"}})
    doc["relationships"][0]["from_columns"] = ["cust", "ver"]
    doc["relationships"][0]["to_columns"] = ["id", "ver"]
    q = compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["customers.region"]))
    assert '"orders"."cust" = "customers"."id" AND "orders"."ver" = "customers"."ver"' in q.sql


def test_chain_of_relationships_pulls_in_intermediate_datasets(doc):
    doc["datasets"].append(
        {"name": "regions", "source": "db.regions", "fields": [
            {"name": "code", "expression": {"sql": "code"}},
            {"name": "country", "expression": {"sql": "country"}}]}
    )
    doc["relationships"].append(
        {"name": "c_r", "from": "customers", "to": "regions", "from_columns": ["region"], "to_columns": ["code"]}
    )
    q = compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["regions.country"]))
    assert q.datasets == ["orders", "customers", "regions"]
    assert q.sql.index('"__customers" AS "customers"') < q.sql.index('"__regions" AS "regions"')


def test_bare_names_resolve_when_unique(doc):
    q = compile_(doc, QueryRequest(metrics=["total"], dimensions=["region"], filters=["region = 'EU'"]))
    assert 'WHERE ("customers"."region" = \'EU\')' in q.sql


def test_ambiguous_bare_field_lists_the_candidates(doc):
    with pytest.raises(QueryError) as exc:
        compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["id"]))
    assert "orders.id" in str(exc.value) and "customers.id" in str(exc.value)


def test_unknown_names_suggest_close_matches(doc):
    with pytest.raises(QueryError) as exc:
        compile_(doc, QueryRequest(metrics=["revnue"]))
    assert "revenue" in str(exc.value)
    with pytest.raises(QueryError) as exc:
        compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["customers.regon"]))
    assert "customers.region" in str(exc.value)


def test_a_query_needs_a_metric(doc):
    with pytest.raises(QueryError):
        compile_(doc, QueryRequest(metrics=[], dimensions=["customers.region"]))


@pytest.mark.parametrize(
    "bad_filter",
    [
        "region IN (SELECT 1)",
        "region = pg_sleep(10)",
        "EXISTS (SELECT 1)",
        "region = 'x'; DROP TABLE orders",
        "(",
    ],
)
def test_unsafe_or_broken_filters_are_rejected(doc, bad_filter):
    with pytest.raises(QueryError):
        compile_(doc, QueryRequest(metrics=["revenue"], filters=[bad_filter]))


def test_ordinary_filters_are_accepted(doc):
    q = compile_(
        doc,
        QueryRequest(
            metrics=["revenue"],
            filters=["region IN ('EU', 'US') AND NOT (amount < 5)", "region LIKE 'E%'", "score IS NOT NULL"],
        ),
    )
    assert "IN ('EU', 'US')" in q.sql and "LIKE 'E%'" in q.sql and "IS NULL" in q.sql


def test_filters_pull_their_dataset_into_the_joins(doc):
    q = compile_(doc, QueryRequest(metrics=["orders.total"], filters=["customers.region = 'EU'"]))
    assert q.datasets == ["orders", "customers"]


def test_datasets_with_no_path_cannot_be_combined(doc):
    doc["datasets"].append({"name": "products", "source": "db.products", "fields": [{"name": "sku", "expression": {"sql": "sku"}}]})
    with pytest.raises(QueryError) as exc:
        compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["products.sku"]))
    assert "cannot join" in str(exc.value)


def test_two_relationships_between_the_same_datasets_are_ambiguous(doc):
    doc["relationships"].append(
        {"name": "o_c_billing", "from": "orders", "to": "customers", "from_columns": ["id"], "to_columns": ["id"]}
    )
    with pytest.raises(QueryError) as exc:
        compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["customers.region"]))
    assert "ambiguous" in str(exc.value) and "o_c_billing" in str(exc.value)
    # a query that does not need the join is unaffected
    assert "JOIN" not in compile_(doc, QueryRequest(metrics=["revenue"])).sql


def test_rebind_uses_the_longest_matching_prefix(doc):
    q = compile_(doc, QueryRequest(metrics=["revenue"]), rebind={"db": "main", "db.orders": "warehouse.sales"})
    assert 'FROM "warehouse"."sales"' in q.sql


def test_rebind_to_empty_prefix_drops_it(doc):
    q = compile_(doc, QueryRequest(metrics=["revenue"]), rebind={"db": ""})
    assert 'FROM "orders"' in q.sql


def test_query_sources_become_subqueries(doc):
    doc["datasets"][0]["source"] = "SELECT * FROM raw.orders WHERE live"
    q = compile_(doc, QueryRequest(metrics=["revenue"]))
    assert "FROM (SELECT * FROM raw.orders WHERE live)" in q.sql


def test_odd_source_names_are_refused(doc):
    doc["datasets"][0]["source"] = "orders; DROP TABLE x"
    with pytest.raises(QueryError):
        compile_(doc, QueryRequest(metrics=["revenue"]))


def test_duplicate_requests_are_collapsed(doc):
    q = compile_(doc, QueryRequest(metrics=["revenue", "revenue"], dimensions=["customers.region", "customers.region"]))
    assert q.columns == ["region", "revenue"]


def test_colliding_output_names_get_unique_aliases(doc):
    q = compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["orders.id", "customers.id"]))
    assert q.columns == ["id", "customers_id", "revenue"]


def test_order_by_accepts_alias_or_reference(doc):
    q = compile_(doc, QueryRequest(metrics=["orders.total"], dimensions=["customers.region"],
                                   order_by=[("orders.total", "desc"), ("customers.region", "asc")], limit=3))
    assert 'ORDER BY "total" DESC, "region" ASC' in q.sql and q.sql.rstrip().endswith("LIMIT 3")


def test_order_by_must_name_a_selected_output(doc):
    with pytest.raises(QueryError):
        compile_(doc, QueryRequest(metrics=["revenue"], order_by=[("customers.score", "asc")]))
    with pytest.raises(QueryError):
        compile_(doc, QueryRequest(metrics=["revenue"], order_by=[("revenue", "sideways")]))


def test_limit_must_be_positive(doc):
    with pytest.raises(QueryError):
        compile_(doc, QueryRequest(metrics=["revenue"], limit=0))


def test_overcount_warning_for_aggregates_over_the_one_side(doc):
    doc["metrics"].append({"name": "score_sum", "expression": {"sql": "SUM(customers.score)"}})
    doc["metrics"].append({"name": "score_max", "expression": {"sql": "MAX(customers.score)"}})
    doc["metrics"].append({"name": "n_cust", "expression": {"sql": "COUNT(DISTINCT customers.id)"}})
    assert compile_(doc, QueryRequest(metrics=["score_sum", "revenue"])).warnings
    assert not compile_(doc, QueryRequest(metrics=["score_max", "n_cust", "revenue"])).warnings


def test_a_bare_bare_metric_prefers_the_model_scoped_one(doc):
    doc["metrics"].append({"name": "total", "expression": {"sql": "SUM(orders.amount) * 2"}})
    assert "* 2" in compile_(doc, QueryRequest(metrics=["total"])).sql
    assert "* 2" not in compile_(doc, QueryRequest(metrics=["orders.total"])).sql


def test_unrunnable_metric_and_field_report_clearly(doc):
    doc["datasets"][1]["fields"][1]["expression"] = {"dialects": [{"dialect": "SNOWFLAKE", "expression": "x::VARCHAR"}]}
    with pytest.raises(QueryError) as exc:
        compile_(doc, QueryRequest(metrics=["revenue"], dimensions=["customers.region"]))
    assert "no expression this engine can run" in str(exc.value)
    # but queries that never touch the field still work
    assert compile_(doc, QueryRequest(metrics=["revenue"])).sql
