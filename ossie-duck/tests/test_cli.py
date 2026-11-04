from __future__ import annotations

import csv
import io
import json

import pytest
import yaml

from ossie_duck.cli import bundled_example, main, format_table


@pytest.fixture
def example(example_path):
    return str(example_path)


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_validate_ok(capsys, example):
    code, out, _ = run(capsys, "validate", example, "--demo-data")
    assert code == 0 and "OK" in out and "5 datasets" in out and "readable" in out


def test_validate_reports_problems_and_fails(capsys, tmp_path, doc):
    doc["version"] = "9.9"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(doc))
    code, _, err = run(capsys, "validate", path)
    assert code == 1 and "9.9" in err and "INVALID" in err


def test_validate_flags_missing_sources(capsys, example):
    code, _, err = run(capsys, "validate", example, "--rebind", "tpcds.public=main")
    assert code == 1 and "store_sales" in err


def test_list_shows_metrics_fields_and_relationships(capsys, example):
    code, out, _ = run(capsys, "list", example)
    assert code == 0
    assert "customer_lifetime_value" in out and "store_sales.total_quantity" in out
    assert "date_dim.d_year" in out and "store_sales_to_store: store_sales -> store" in out


def test_sql_prints_without_running(capsys, example):
    code, out, _ = run(capsys, "sql", example, "-m", "total_sales", "-d", "item.i_brand", "--rebind", "tpcds.public=main")
    assert code == 0 and out.startswith("WITH") and 'LEFT JOIN "__item"' in out and '"main"."store_sales"' in out


def test_query_table_csv_and_json(capsys, example):
    args = ("query", example, "--demo-data", "-m", "total_sales,total_profit", "-d", "date_dim.d_year")
    code, out, _ = run(capsys, *args)
    assert code == 0 and "d_year" in out and "(2 rows)" in out

    code, out, _ = run(capsys, *args, "--format", "csv")
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["d_year", "total_sales", "total_profit"] and [r[0] for r in rows[1:]] == ["2023", "2024"]

    code, out, _ = run(capsys, *args, "--format", "json")
    data = json.loads(out)
    assert [d["d_year"] for d in data] == [2023, 2024]


def test_query_options(capsys, example):
    code, out, _ = run(
        capsys, "query", example, "--demo-data", "-m", "total_sales", "-d", "item.i_category",
        "-f", "store.s_state = 'CA'", "--order", "total_sales:desc", "--limit", 2, "--show-sql",
    )
    assert code == 0 and "WHERE" in out and "LIMIT 2" in out and "(2 rows)" in out


def test_query_against_a_database_file(capsys, example, tmp_path):
    import duckdb

    from ossie_duck.sample_data import load_synthetic_tpcds

    db = tmp_path / "t.duckdb"
    con = duckdb.connect(str(db))
    load_synthetic_tpcds(con)
    con.close()
    code, out, _ = run(capsys, "query", example, "--db", db, "--rebind", "tpcds.public=main", "-m", "store_sales.total_quantity")
    assert code == 0 and "33000" in out


def test_errors_exit_nonzero_with_a_message(capsys, example):
    code, _, err = run(capsys, "query", example, "--demo-data", "-m", "total_salez")
    assert code == 1 and "unknown metric" in err and "total_sales" in err
    code, _, err = run(capsys, "validate", "/no/such/file.yaml")
    assert code == 1 and "error:" in err
    code, _, err = run(capsys, "sql", example, "-m", "total_sales", "--rebind", "oops")
    assert code == 1 and "PREFIX=TARGET" in err


def test_warnings_go_to_stderr(capsys, example):
    code, out, err = run(capsys, "query", example, "--demo-data", "-m", "store_productivity", "-d", "store.s_state")
    assert code == 0 and "overcounted" in err and "overcounted" not in out


def test_demo_runs_the_bundled_model(capsys):
    assert bundled_example().is_file()
    code, out, _ = run(capsys, "demo")
    assert code == 0 and "Sales and profit by year" in out and "Month-over-month" in out


def test_ask_needs_credentials(capsys, example, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code, _, err = run(capsys, "ask", example, "what were sales?", "--demo-data")
    assert code == 1 and "error:" in err


def test_table_formatting_aligns_numbers_and_handles_nulls():
    text = format_table(["name", "n"], [("a", 5), ("bb", None), ("c", 1234)])
    lines = text.splitlines()
    assert lines[0].split() == ["name", "n"]
    assert lines[2].endswith("   5") and lines[3].endswith("NULL") and lines[4].endswith("1234")
    assert lines[-1] == "(3 rows)"


# ------------------------------------------------------------------ serve / mcp


KEY = "cli-test-key-0123456789abcdef"


@pytest.fixture
def captured(monkeypatch):
    """Replace uvicorn.run so the command builds its app but does not listen."""
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append((app, kw)))
    monkeypatch.delenv("OSSIE_DUCK_API_KEYS", raising=False)
    return calls


def test_serve_refuses_to_listen_on_the_network_without_keys(capsys, example, captured):
    code, _, err = run(capsys, "serve", example, "--demo-data", "--host", "0.0.0.0")
    assert code == 1 and "refusing to listen" in err and "OSSIE_DUCK_API_KEYS" in err and not captured


def test_mcp_http_refuses_the_same_way(capsys, example, captured):
    code, _, err = run(capsys, "mcp", example, "--demo-data", "--transport", "http", "--host", "0.0.0.0")
    assert code == 1 and "refusing to listen" in err and not captured


def test_short_keys_are_rejected(capsys, example, captured, monkeypatch):
    monkeypatch.setenv("OSSIE_DUCK_API_KEYS", "short")
    code, _, err = run(capsys, "serve", example, "--demo-data")
    assert code == 1 and "at least 16" in err and not captured


def test_serve_on_loopback_needs_no_key(capsys, example, captured):
    from fastapi.testclient import TestClient

    code, _, err = run(capsys, "serve", example, "--demo-data", "--port", "8123")
    assert code == 0 and "NO authentication (loopback only)" in err
    app, kw = captured[0]
    assert kw["host"] == "127.0.0.1" and kw["port"] == 8123
    assert TestClient(app).get("/catalog").status_code == 200


def test_serve_with_keys_limits_and_base_filter_all_take_effect(capsys, example, captured, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("OSSIE_DUCK_API_KEYS", KEY)
    code, _, err = run(
        capsys, "serve", example, "--demo-data", "--host", "0.0.0.0", "--max-rows", "4",
        "--base-filter", "store.s_state = 'CA'", "--cors-origin", "https://dash.example.com",
    )
    assert code == 0 and "API key required (1 configured)" in err and "max 4 rows" in err and "s_state" in err
    client = TestClient(captured[0][0])
    assert client.get("/catalog").status_code == 401
    r = client.post("/query", headers={"X-API-Key": KEY}, json={"metrics": ["total_sales"], "dimensions": ["date_dim.d_date"]})
    body = r.json()
    assert r.status_code == 200 and body["row_count"] == 4 and body["truncated"]
    states = client.post("/query", headers={"X-API-Key": KEY}, json={"metrics": ["total_sales"], "dimensions": ["store.s_state"]})
    assert [row[0] for row in states.json()["rows"]] == ["CA"]


def test_mcp_http_app_is_wrapped_in_auth(capsys, example, captured, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.setenv("OSSIE_DUCK_API_KEYS", KEY)
    code, _, err = run(capsys, "mcp", example, "--demo-data", "--transport", "http", "--port", "8124")
    assert code == 0 and "streamable HTTP at /mcp" in err
    app, kw = captured[0]
    assert kw["port"] == 8124
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200  # liveness stays open
        assert client.post("/mcp", json={}).status_code == 401
        assert client.post("/mcp", json={}, headers={"X-API-Key": "wrong-wrong-wrong-wrong"}).status_code == 401


def test_mcp_stdio_runs_the_server_and_keeps_stdout_clean(capsys, example, monkeypatch):
    from mcp.server.mcpserver import MCPServer

    transports = []
    monkeypatch.setattr(MCPServer, "run", lambda self, transport="stdio", **kw: transports.append(transport))
    code, out, err = run(capsys, "mcp", example, "--demo-data")
    assert code == 0 and transports == ["stdio"]
    assert out == "" and "on stdio" in err  # stdout is the protocol channel: nothing else may be written there


def test_bad_service_settings_are_clean_errors(capsys, example, captured):
    code, _, err = run(capsys, "serve", example, "--demo-data", "--timeout", "0")
    assert code == 1 and "timeout_s must be positive" in err
    code, _, err = run(capsys, "serve", example, "--demo-data", "--max-rows", "0")
    assert code == 1 and "max_rows" in err
    code, _, err = run(capsys, "serve", example, "--demo-data", "--base-filter", "store.s_state IN (SELECT 1)")
    assert code == 1 and "not allowed" in err
    assert not captured


# ------------------------------------------------------------------ friendly errors for newcomers


def test_missing_database_file_is_a_clean_error(capsys, example, tmp_path):
    code, _, err = run(capsys, "query", example, "--db", tmp_path / "nope.duckdb", "-m", "total_sales")
    assert code == 1 and "database file not found" in err and "Traceback" not in err


def test_a_file_that_is_not_a_database_is_a_clean_error(capsys, example, tmp_path):
    bogus = tmp_path / "bogus.duckdb"
    bogus.write_text("this is not a database")
    code, _, err = run(capsys, "query", example, "--db", bogus, "-m", "total_sales")
    assert code == 1 and err.startswith("error:") and "Traceback" not in err


def test_forgetting_rebind_explains_what_to_do(capsys, example, tmp_path):
    import duckdb

    from ossie_duck.sample_data import load_synthetic_tpcds

    db = tmp_path / "t.duckdb"
    con = duckdb.connect(str(db)); load_synthetic_tpcds(con); con.close()
    code, _, err = run(capsys, "query", example, "--db", db, "-m", "total_sales")
    assert code == 1 and "Catalog Error" in err and "--rebind tpcds.public=main" in err and "Generated SQL:" in err
    code, _, err = run(capsys, "validate", example, "--db", db)  # validate gives the same hint, without the SQL dump
    assert code == 1 and "--rebind tpcds.public=main" in err and "WITH" not in err
