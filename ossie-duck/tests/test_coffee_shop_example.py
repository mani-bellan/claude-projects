"""The README walkthrough: every number is recomputed from the CSV files in plain Python."""

from __future__ import annotations

import csv
import importlib.util
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from ossie_duck import QueryRequest, SemanticService, load_model
from ossie_duck.cli import main

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "coffee_shop"
MODEL = EXAMPLE_DIR / "coffee_shop_model.yaml"


def _rows(name: str) -> list[dict[str, str]]:
    with open(EXAMPLE_DIR / f"{name}.csv", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    spec = importlib.util.spec_from_file_location("coffee_build_db", EXAMPLE_DIR / "build_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(tmp_path_factory.mktemp("coffee") / "coffee_shop.duckdb")


@pytest.fixture(scope="module")
def service(db_path):
    import duckdb

    model = load_model(MODEL)
    return SemanticService(model, duckdb.connect(str(db_path), read_only=True), {"shop.public": "main"})


@pytest.fixture(scope="module")
def expected():
    """Ground truth from the raw CSVs, with no engine involved."""
    country_of = {r["customer_id"]: r["country"] for r in _rows("customers")}
    by_country, by_month, by_product_india = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
    orders_in_month: dict[str, set[str]] = defaultdict(set)
    buyers: set[str] = set()
    for r in _rows("orders"):
        total = Decimal(r["quantity"]) * Decimal(r["unit_price"])
        by_country[country_of[r["customer_id"]]] += total
        month = r["order_date"][:7]
        by_month[month] += total
        orders_in_month[month].add(r["order_id"])
        buyers.add(r["customer_id"])
        if country_of[r["customer_id"]] == "India":
            by_product_india[r["product"]] += total
    return {
        "by_country": dict(by_country),
        "by_month": dict(by_month),
        "orders_in_month": {m: len(ids) for m, ids in orders_in_month.items()},
        "by_product_india": dict(by_product_india),
        "total": sum(by_country.values()),
        "buyers": len(buyers),
    }


def test_the_model_is_clean():
    model = load_model(MODEL)
    assert model.issues == []
    assert {m.ref for m in model.all_metrics()} == {"revenue", "average_order_value", "active_customers", "orders.order_count"}


def test_revenue_by_country(service, expected):
    got = service.query({"metrics": ["revenue"], "dimensions": ["customers.country"]})
    assert {country: Decimal(str(v)) for country, v in got["rows"]} == expected["by_country"]


def test_monthly_trend_and_average_order_value(service, expected):
    got = service.query({"metrics": ["revenue", "average_order_value"], "dimensions": ["orders.order_month"]})
    assert [r[0] for r in got["rows"]] == sorted(expected["by_month"])  # sorted by month
    for month, revenue, aov in got["rows"]:
        assert Decimal(str(revenue)) == expected["by_month"][month]
        assert aov == pytest.approx(float(expected["by_month"][month]) / expected["orders_in_month"][month])


def test_top_products_in_india_match_the_readme(service, expected):
    got = service.query(
        {
            "metrics": ["revenue", "orders.order_count"],
            "dimensions": ["orders.product"],
            "filters": ["customers.country = 'India'"],
            "order_by": ["revenue:desc"],
            "limit": 3,
        }
    )
    ranked = sorted(expected["by_product_india"].items(), key=lambda kv: kv[1], reverse=True)[:3]
    assert [(r[0], Decimal(str(r[1]))) for r in got["rows"]] == ranked
    assert [r[0] for r in got["rows"]] == ["Espresso Beans", "Cold Brew Kit", "Green Tea"]
    assert got["rows"][0][2] == 4  # four Espresso Beans orders from India


def test_headline_numbers(service, expected):
    got = service.query({"metrics": ["active_customers", "revenue"]})
    assert got["rows"][0][0] == expected["buyers"] == 8
    assert Decimal(str(got["rows"][0][1])) == expected["total"] == Decimal("688.25")


def test_the_documented_cli_commands_work(db_path, capsys):
    args = ["--db", str(db_path), "--rebind", "shop.public=main"]
    assert main(["validate", str(MODEL), *args]) == 0
    capsys.readouterr()
    assert main(["query", str(MODEL), *args, "-m", "revenue", "-d", "customers.country", "--order", "revenue:desc"]) == 0
    out = capsys.readouterr().out
    lines = [ln.split() for ln in out.splitlines()[2:6]]
    assert lines == [["India", "231.25"], ["UK", "184.75"], ["USA", "172.25"], ["Germany", "100.00"]]


def test_changing_a_definition_changes_every_answer(db_path, tmp_path):
    """The README's "define once" exercise: edit one line of the model, and the numbers follow."""
    import duckdb

    text = MODEL.read_text()
    old = "  - name: revenue\n    expression: { sql: SUM(orders.line_total) }\n"
    new = (
        "  - name: revenue\n"
        "    expression: { sql: \"SUM(CASE WHEN orders.product <> 'Ceramic Mug' THEN orders.line_total ELSE 0 END)\" }\n"
    )
    assert text.count(old) == 1, "the README tells readers to edit exactly this line"
    edited = tmp_path / "edited.yaml"
    edited.write_text(text.replace(old, new))

    svc = SemanticService(load_model(edited), duckdb.connect(str(db_path), read_only=True), {"shop.public": "main"})
    got = svc.query({"metrics": ["revenue"], "dimensions": ["customers.country"], "order_by": ["revenue:desc"]})
    assert [(c, Decimal(str(v))) for c, v in got["rows"]] == [
        ("India", Decimal("219.25")), ("UK", Decimal("172.75")), ("USA", Decimal("124.25")), ("Germany", Decimal("64.00")),
    ]
