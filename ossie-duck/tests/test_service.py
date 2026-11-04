from __future__ import annotations

import datetime as dt
import json
import threading
import time
from decimal import Decimal

import duckdb
import pytest

from ossie_duck import QueryError, QueryRequest
from ossie_duck.service import SemanticService, json_value, to_csv


@pytest.fixture
def service(model, con):
    return SemanticService(model, con, rebind={"tpcds.public": "main"})


def test_catalog_is_json_and_hides_physical_sources(service):
    cat = service.catalog()
    json.dumps(cat)  # must be serialisable as-is
    assert cat["name"] == "tpcds_retail_model" and cat["spec_version"] == "0.2.0.dev0"
    assert "retail analytics" in cat["instructions"]
    refs = {m["ref"] for m in cat["metrics"]}
    assert {"total_sales", "store_sales.total_quantity"} <= refs
    clv = next(m for m in cat["metrics"] if m["ref"] == "customer_lifetime_value")
    assert clv["scope"] == "model" and "CLV" in clv["synonyms"]
    qty = next(m for m in cat["metrics"] if m["name"] == "total_quantity")
    assert qty["scope"] == "dataset" and qty["dataset"] == "store_sales"
    year = next(f for ds in cat["datasets"] for f in ds["fields"] if f["ref"] == "date_dim.d_year")
    assert year["is_time"] is True and year["datatype"] == "Integer"
    assert "tpcds.public" not in json.dumps(cat)  # no table names leak
    assert cat["relationships"][0]["from"] == "store_sales"


def test_query_returns_json_safe_rows(service):
    out = service.query({"metrics": ["total_sales"], "dimensions": ["date_dim.d_year"]})
    assert out["columns"] == ["d_year", "total_sales"] and out["row_count"] == 2 and not out["truncated"]
    assert [r[0] for r in out["rows"]] == [2023, 2024] and isinstance(out["rows"][0][1], float)
    json.dumps(out)
    assert "sql" not in out


def test_include_sql_and_explain(service):
    request = {"metrics": ["total_sales"], "dimensions": ["item.i_brand"]}
    assert service.query(request, include_sql=True)["sql"].startswith("WITH")
    plan = service.explain(request)
    assert plan["root_dataset"] == "store_sales" and plan["datasets"] == ["store_sales", "item"]
    assert plan["columns"] == ["i_brand", "total_sales"]


def test_accepts_a_prebuilt_request_object(service):
    assert service.query(QueryRequest(metrics=["total_sales"]))["row_count"] == 1


def test_row_cap_truncates_and_says_so(model, con):
    capped = SemanticService(model, con, {"tpcds.public": "main"}, max_rows=5)
    out = capped.query({"metrics": ["total_sales"], "dimensions": ["date_dim.d_date"]})
    assert out["row_count"] == 5 and out["truncated"] is True and out["max_rows"] == 5
    assert any("cut off at 5 rows" in w for w in out["warnings"])
    exact = capped.query({"metrics": ["total_sales"], "dimensions": ["store.s_state"], "limit": 5})
    assert exact["row_count"] == 5 and exact["truncated"] is False  # exactly at the cap is not truncation


def test_base_filters_apply_to_every_query(model, con):
    open_ = SemanticService(model, con, {"tpcds.public": "main"})
    ca_only = SemanticService(model, con, {"tpcds.public": "main"}, base_filters=["store.s_state = 'CA'"])
    everything = open_.query({"metrics": ["total_sales"]})["rows"][0][0]
    california = ca_only.query({"metrics": ["total_sales"]})["rows"][0][0]
    assert 0 < california < everything
    states = ca_only.query({"metrics": ["total_sales"], "dimensions": ["store.s_state"]})["rows"]
    assert [r[0] for r in states] == ["CA"]
    assert "s_state" in ca_only.explain({"metrics": ["total_sales"]})["sql"]
    # a caller cannot widen the scope with an OR in their own filter
    wide = ca_only.query({"metrics": ["total_sales"], "filters": ["store.s_state = 'NY' OR store.s_state = 'CA'"]})
    assert wide["rows"][0][0] == california


def test_bad_base_filter_fails_at_startup(model, con):
    with pytest.raises(QueryError):
        SemanticService(model, con, base_filters=["store.s_state IN (SELECT 1)"])
    with pytest.raises(QueryError):
        SemanticService(model, con, base_filters=["no_such_field = 1"])


def test_bad_limits_are_refused(model, con):
    with pytest.raises(ValueError):
        SemanticService(model, con, max_rows=0)
    with pytest.raises(ValueError):
        SemanticService(model, con, timeout_s=0)


def test_errors_are_query_errors_without_sql(service):
    with pytest.raises(QueryError) as exc:
        service.query({"metrics": ["total_salez"]})
    assert "total_sales" in str(exc.value)
    with pytest.raises(QueryError) as exc:  # window metric without its grouping: DuckDB rejects it
        service.query({"metrics": ["cumulative_sales"]})
    assert "rejected" in str(exc.value) and "SELECT" not in str(exc.value) and "WITH" not in str(exc.value)
    with pytest.raises(QueryError):
        service.query({"metrics": ["total_sales"], "sql": "DROP TABLE x"})


def test_timeout_cancels_a_slow_query(doc):
    from ossie_duck import parse_model

    # A streaming aggregate over a generated range: slow, but it stores nothing.
    doc["datasets"][0]["source"] = "SELECT i AS id, 1 AS cust_id, 1 AS amount FROM range(100000000000) t(i)"
    svc = SemanticService(parse_model(doc), duckdb.connect(), timeout_s=0.2)
    t0 = time.monotonic()
    with pytest.raises(QueryError) as exc:
        svc.query({"metrics": ["orders.total"]})
    assert "cancelled" in str(exc.value) and time.monotonic() - t0 < 10
    # the connection survives, and a fast query on it still works
    doc["datasets"][0]["source"] = "SELECT 1 AS id, 1 AS cust_id, 5 AS amount"
    quick = SemanticService(parse_model(doc), svc.con, timeout_s=5)
    assert quick.query({"metrics": ["orders.total"]})["rows"] == [[5]]


def test_concurrent_queries_do_not_interfere(service):
    results, errors = [], []

    def work(year):
        try:
            out = service.query({"metrics": ["total_sales"], "filters": [f"date_dim.d_year = {year}"]})
            results.append((year, out["rows"][0][0]))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(2023 + i % 2,)) for i in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(results) == 16
    assert len({v for y, v in results if y == 2023}) == 1 and len({v for y, v in results if y == 2024}) == 1


def test_json_value_conversions():
    assert json_value(Decimal("1.50")) == 1.5
    assert json_value(dt.date(2024, 1, 2)) == "2024-01-02"
    assert json_value(dt.datetime(2024, 1, 2, 3, 4, 5)) == "2024-01-02T03:04:05"
    assert json_value(float("nan")) is None and json_value(float("inf")) is None
    assert json_value([Decimal("2"), None]) == [2.0, None]
    assert json_value(b"ab") == "b'ab'" and json_value(True) is True and json_value(None) is None


def test_csv_neutralises_spreadsheet_formulas():
    text = to_csv(["name", "n"], [("=HYPERLINK(\"http://x\")", 5), ("-cmd", -3), ("plain", None), ("a,b", 1.5)])
    lines = text.splitlines()
    assert lines[0] == "name,n"
    assert lines[1].startswith("\"'=HYPERLINK") and lines[2] == "'-cmd,-3"  # text escaped, number untouched
    assert lines[3] == "plain," and lines[4] == '"a,b",1.5'
