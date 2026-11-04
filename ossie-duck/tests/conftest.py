from __future__ import annotations

import copy
from pathlib import Path

import duckdb
import pytest

from ossie_duck import Engine, load_model
from ossie_duck.sample_data import load_synthetic_tpcds

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "tpcds_semantic_model.yaml"

_BASE_DOC = {
    "version": "0.2.0.dev0",
    "name": "t",
    "datasets": [
        {
            "name": "orders",
            "source": "db.orders",
            "fields": [
                {"name": "id", "expression": {"sql": "id"}},
                {"name": "cust", "expression": {"sql": "cust_id"}},
                {"name": "amount", "expression": {"sql": "amount"}},
            ],
            "metrics": [{"name": "total", "expression": {"sql": "SUM(amount)"}}],
        },
        {
            "name": "customers",
            "source": "db.customers",
            "fields": [
                {"name": "id", "expression": {"sql": "id"}},
                {"name": "region", "expression": {"sql": "region"}},
                {"name": "score", "expression": {"sql": "score"}},
            ],
        },
    ],
    "relationships": [
        {"name": "o_c", "from": "orders", "to": "customers", "from_columns": ["cust"], "to_columns": ["id"]}
    ],
    "metrics": [{"name": "revenue", "expression": {"sql": "SUM(orders.amount)"}}],
}


@pytest.fixture
def doc() -> dict:
    """A small valid model document (a fresh deep copy per test)."""
    return copy.deepcopy(_BASE_DOC)


@pytest.fixture(scope="session")
def example_path() -> Path:
    return EXAMPLE


@pytest.fixture(scope="session")
def model():
    return load_model(EXAMPLE)


@pytest.fixture
def con():
    connection = duckdb.connect()
    load_synthetic_tpcds(connection)
    yield connection
    connection.close()


@pytest.fixture
def engine(model, con):
    return Engine(model, con, rebind={"tpcds.public": "main"})
