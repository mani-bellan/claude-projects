from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from ossie_duck.auth import ApiKeyMiddleware, is_loopback, keys_from_env, parse_keys
from ossie_duck.rest import create_app
from ossie_duck.service import SemanticService

KEY = "test-key-0123456789abcdef"
OTHER = "second-key-0123456789abcd"
BEARER = {"Authorization": f"Bearer {KEY}"}


@pytest.fixture
def service(model, con):
    return SemanticService(model, con, {"tpcds.public": "main"})


@pytest.fixture
def open_client(service):
    return TestClient(create_app(service))


@pytest.fixture
def client(service):
    return TestClient(create_app(service, api_keys=[KEY, OTHER]))


# ------------------------------------------------------------------ endpoints


def test_health_and_catalog(open_client):
    assert open_client.get("/health").json() == {"status": "ok", "model": "tpcds_retail_model"}
    cat = open_client.get("/catalog").json()
    assert "total_sales" in {m["ref"] for m in cat["metrics"]} and cat["limits"]["max_rows"] == 1000


def test_post_query_json(open_client):
    r = open_client.post("/query", json={"metrics": ["total_sales"], "dimensions": ["date_dim.d_year"]})
    assert r.status_code == 200
    body = r.json()
    assert body["columns"] == ["d_year", "total_sales"] and [row[0] for row in body["rows"]] == [2023, 2024]
    assert "sql" not in body


def test_post_query_all_options(open_client):
    r = open_client.post(
        "/query",
        json={
            "metrics": ["total_sales"],
            "dimensions": ["item.i_category"],
            "filters": ["store.s_state = 'CA'"],
            "order_by": [{"by": "total_sales", "direction": "desc"}],
            "limit": 2,
            "include_sql": True,
        },
    )
    body = r.json()
    assert r.status_code == 200 and body["row_count"] == 2 and body["sql"].startswith("WITH")
    totals = [row[1] for row in body["rows"]]
    assert totals == sorted(totals, reverse=True)


def test_order_by_string_shorthand(open_client):
    r = open_client.post("/query", json={"metrics": ["total_sales"], "dimensions": ["item.i_category"], "order_by": ["total_sales:desc"]})
    totals = [row[1] for row in r.json()["rows"]]
    assert r.status_code == 200 and totals == sorted(totals, reverse=True)


def test_get_query_csv_for_url_imports(open_client):
    r = open_client.get(
        "/query",
        params=[("metric", "total_sales"), ("metric", "total_profit"), ("dimension", "date_dim.d_year"), ("format", "csv")],
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["d_year", "total_sales", "total_profit"] and len(rows) == 3
    assert r.headers["x-row-count"] == "2" and r.headers["x-truncated"] == "false"


def test_get_query_with_repeated_filters_and_order(open_client):
    r = open_client.get(
        "/query",
        params=[("metric", "total_sales"), ("dimension", "item.i_category"), ("filter", "store.s_state = 'CA'"),
                ("filter", "date_dim.d_year = 2024"), ("order", "total_sales:desc"), ("limit", "3")],
    )
    assert r.status_code == 200 and r.json()["row_count"] == 3


def test_post_query_csv(open_client):
    r = open_client.post("/query?format=csv", json={"metrics": ["total_sales"], "dimensions": ["store.s_state"]})
    assert r.text.splitlines()[0] == "s_state,total_sales" and len(r.text.splitlines()) == 7


def test_csv_reports_truncation_in_a_header(model, con):
    capped = TestClient(create_app(SemanticService(model, con, {"tpcds.public": "main"}, max_rows=3)))
    r = capped.get("/query", params={"metric": "total_sales", "dimension": "date_dim.d_date", "format": "csv"})
    assert r.headers["x-truncated"] == "true" and len(r.text.splitlines()) == 4


def test_sql_endpoint_compiles_without_running(open_client):
    r = open_client.post("/sql", json={"metrics": ["total_sales"], "dimensions": ["item.i_brand"]})
    assert r.status_code == 200 and r.json()["root_dataset"] == "store_sales" and "LEFT JOIN" in r.json()["sql"]


# ------------------------------------------------------------------ errors


def test_query_errors_are_400_with_a_helpful_message(open_client):
    r = open_client.post("/query", json={"metrics": ["total_salez"]})
    assert r.status_code == 400 and "total_sales" in r.json()["error"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"metrics": []},
        {"metrics": ["a"], "sql": "select 1"},
        {"metrics": ["a"], "limit": 0},
        {"metrics": [1]},
        {"metrics": ["a"], "filters": ["x" * 501]},
        {"metrics": ["a"], "order_by": [{"by": "a", "direction": "sideways"}]},
    ],
)
def test_malformed_bodies_are_400_not_500(open_client, body):
    r = open_client.post("/query", json=body)
    assert r.status_code == 400 and "invalid request" in r.json()["error"]


def test_unsafe_filter_is_a_400(open_client):
    r = open_client.post("/query", json={"metrics": ["total_sales"], "filters": ["store.s_state IN (SELECT 1)"]})
    assert r.status_code == 400 and "not allowed" in r.json()["error"]


def test_unexpected_errors_are_500_without_details(service):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail /var/db/x")

    service.query = boom  # type: ignore[method-assign]
    r = TestClient(create_app(service), raise_server_exceptions=False).post("/query", json={"metrics": ["total_sales"]})
    assert r.status_code == 500 and r.json() == {"error": "internal error"}


def test_base_filters_hold_over_http(model, con):
    scoped = TestClient(create_app(SemanticService(model, con, {"tpcds.public": "main"}, base_filters=["store.s_state = 'CA'"])))
    r = scoped.post("/query", json={"metrics": ["total_sales"], "dimensions": ["store.s_state"]})
    assert [row[0] for row in r.json()["rows"]] == ["CA"]


# ------------------------------------------------------------------ auth


def test_health_is_open_everything_else_needs_a_key(client):
    assert client.get("/health").status_code == 200
    for method, path in (("get", "/catalog"), ("post", "/query"), ("get", "/query"), ("post", "/sql"), ("get", "/docs")):
        r = getattr(client, method)(path)
        assert r.status_code == 401, path
        assert r.json() == {"error": "missing or invalid API key"} and "Bearer" in r.headers["www-authenticate"]


def test_bearer_and_x_api_key_both_work_and_any_configured_key(client):
    assert client.get("/catalog", headers=BEARER).status_code == 200
    assert client.get("/catalog", headers={"X-API-Key": KEY}).status_code == 200
    assert client.get("/catalog", headers={"Authorization": f"Bearer {OTHER}"}).status_code == 200
    assert client.get("/catalog", headers={"Authorization": f"bearer {KEY}"}).status_code == 200  # scheme is case-insensitive


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong"}, {"Authorization": KEY}, {"X-API-Key": KEY[:-1]}, {"X-API-Key": KEY + "x"}, {"Authorization": "Basic " + KEY}],
)
def test_wrong_keys_are_refused(client, headers):
    assert client.get("/catalog", headers=headers).status_code == 401


def test_keys_in_the_url_are_not_accepted(client):
    assert client.get("/catalog", params={"api_key": KEY}).status_code == 401


def test_query_still_validates_after_auth(client):
    assert client.post("/query", headers=BEARER, json={"metrics": ["nope"]}).status_code == 400


def test_cors_preflight_is_answered_without_a_key(service):
    c = TestClient(create_app(service, api_keys=[KEY], cors_origins=["https://dash.example.com"]))
    pre = c.options(
        "/query",
        headers={"Origin": "https://dash.example.com", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"},
    )
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == "https://dash.example.com"
    # the real request still needs the key
    assert c.post("/query", json={"metrics": ["total_sales"]}, headers={"Origin": "https://dash.example.com"}).status_code == 401
    ok = c.post("/query", json={"metrics": ["total_sales"]}, headers={**BEARER, "Origin": "https://dash.example.com"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "https://dash.example.com"


def test_other_origins_get_no_cors_headers(service):
    c = TestClient(create_app(service, cors_origins=["https://dash.example.com"]))
    r = c.get("/catalog", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


# ------------------------------------------------------------------ key helpers


def test_parse_keys():
    assert parse_keys(None) == [] and parse_keys("") == []
    assert parse_keys(f" {KEY} , {OTHER} ") == [KEY, OTHER]
    with pytest.raises(ValueError) as exc:
        parse_keys("short")
    assert "at least 16" in str(exc.value)


def test_keys_from_env():
    assert keys_from_env({"OSSIE_DUCK_API_KEYS": KEY}) == [KEY] and keys_from_env({}) == []


def test_is_loopback():
    assert is_loopback("127.0.0.1") and is_loopback("::1") and is_loopback("localhost")
    assert not is_loopback("0.0.0.0") and not is_loopback("192.168.1.5")


def test_middleware_ignores_non_http_scopes_gracefully():
    import asyncio

    calls = []

    async def inner(scope, receive, send):
        calls.append(scope["type"])

    mw = ApiKeyMiddleware(inner, keys=[KEY])
    sent = []

    async def send(msg):
        sent.append(msg)

    asyncio.run(mw({"type": "lifespan"}, None, send))
    assert calls == ["lifespan"]
    asyncio.run(mw({"type": "websocket", "headers": []}, None, send))
    assert sent == [{"type": "websocket.close", "code": 1008}] and calls == ["lifespan"]
