"""The natural-language layer, driven by a fake client (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ossie_duck import QueryError
from ossie_duck.ask import TOOL, ask, build_system_prompt, request_from_tool_input


class FakeClient:
    def __init__(self, *tool_inputs):
        self.queue = list(tool_inputs)
        self.calls: list[dict] = []
        self.messages = self  # client.messages.create(...)

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        data = self.queue.pop(0)
        block = SimpleNamespace(type="tool_use", id=f"toolu_{len(self.calls)}", name="semantic_query", input=data)
        return SimpleNamespace(content=[block])


def test_answers_by_running_the_chosen_query(engine):
    client = FakeClient(
        {"metrics": ["total_sales"], "dimensions": ["date_dim.d_year"], "order_by": [{"by": "d_year", "direction": "desc"}]}
    )
    answer = ask(engine, "What were sales per year?", client=client, model_id="test-model")
    assert answer.result.columns == ["d_year", "total_sales"]
    assert [r[0] for r in answer.result.rows] == [2024, 2023]
    call = client.calls[0]
    assert call["model"] == "test-model"
    assert call["tool_choice"] == {"type": "tool", "name": "semantic_query"}
    assert call["tools"] == [TOOL]


def test_a_rejected_query_is_sent_back_once_for_correction(engine):
    client = FakeClient({"metrics": ["total_revenu"]}, {"metrics": ["total_sales"]})
    answer = ask(engine, "total revenue?", client=client)
    assert answer.request.metrics == ["total_sales"] and len(client.calls) == 2
    feedback = client.calls[1]["messages"][-1]["content"][0]
    assert feedback["is_error"] and "total_sales" in feedback["content"]  # suggestion reached the model


def test_gives_up_after_max_attempts(engine):
    client = FakeClient({"metrics": ["nope"]}, {"metrics": ["still_nope"]})
    with pytest.raises(QueryError):
        ask(engine, "?", client=client, max_attempts=2)
    assert len(client.calls) == 2


def test_unsafe_filters_from_the_model_never_reach_duckdb(engine):
    client = FakeClient(
        {"metrics": ["total_sales"], "filters": ["store.s_state IN (SELECT 'CA')"]},
        {"metrics": ["total_sales"], "filters": ["store.s_state = 'CA'"]},
    )
    answer = ask(engine, "CA sales", client=client)
    assert "SELECT 'CA'" not in answer.result.sql and len(client.calls) == 2


def test_system_prompt_carries_the_models_own_guidance(model):
    prompt = build_system_prompt(model)
    assert "Use this semantic model for retail analytics" in prompt  # model-level ai_context
    assert "customer_lifetime_value" in prompt and "CLV" in prompt  # metric synonyms
    assert "store.s_state" in prompt and "date_dim.d_year" in prompt and "time" in prompt


def test_missing_tool_call_is_an_error(engine):
    class NoTool(FakeClient):
        def create(self, **kwargs):
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="I refuse")])

    with pytest.raises(QueryError):
        ask(engine, "?", client=NoTool())


def test_tool_input_is_validated():
    assert request_from_tool_input({"metrics": "total_sales"}).metrics == ["total_sales"]
    for bad in ({"metrics": [1]}, {"metrics": ["a"], "order_by": [5]}, {"metrics": ["a"], "limit": "3"}):
        with pytest.raises(QueryError):
            request_from_tool_input(bad)


def test_default_client_needs_a_key(engine, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(QueryError):
        ask(engine, "?")
