"""QueryRequest.from_dict: the one parser behind REST, MCP and the ask layer."""

from __future__ import annotations

import pytest

from ossie_duck import QueryError, QueryRequest
from ossie_duck.compiler import validate_filter


def test_full_payload():
    req = QueryRequest.from_dict(
        {
            "metrics": ["a", "b"],
            "dimensions": ["x.y"],
            "filters": ["x.y = 1"],
            "order_by": [{"by": "a", "direction": "desc"}, "b", "x.y:desc"],
            "limit": 5,
        }
    )
    assert req.metrics == ["a", "b"] and req.dimensions == ["x.y"] and req.filters == ["x.y = 1"]
    assert req.order_by == [("a", "desc"), ("b", "asc"), ("x.y", "desc")] and req.limit == 5


def test_single_strings_become_lists_and_missing_keys_default():
    req = QueryRequest.from_dict({"metrics": "total_sales"})
    assert req.metrics == ["total_sales"] and req.dimensions == [] and req.order_by == [] and req.limit is None


@pytest.mark.parametrize(
    "bad",
    [
        [],  # not an object
        {"metrics": [1]},
        {"metrics": ["a"], "dimensions": {"x": 1}},
        {"metrics": ["a"], "order_by": [5]},
        {"metrics": ["a"], "order_by": [{"direction": "asc"}]},
        {"metrics": ["a"], "limit": "3"},
        {"metrics": ["a"], "limit": True},
        {"metrics": ["a"], "sql": "select 1"},  # unknown fields are refused, not ignored
    ],
)
def test_malformed_payloads_are_rejected(bad):
    with pytest.raises(QueryError):
        QueryRequest.from_dict(bad)


def test_unknown_field_message_lists_the_allowed_ones():
    with pytest.raises(QueryError) as exc:
        QueryRequest.from_dict({"metrics": ["a"], "sql": "x"})
    assert "sql" in str(exc.value) and "dimensions" in str(exc.value)


def test_validate_filter(model):
    validate_filter(model, "store.s_state = 'CA'")
    for bad in ("store.s_state IN (SELECT 1)", "nonexistent = 1", "("):
        with pytest.raises(QueryError):
            validate_filter(model, bad)
