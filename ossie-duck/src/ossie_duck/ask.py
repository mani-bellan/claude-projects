"""Optional natural-language layer.

The LLM never writes SQL. It is given the model's catalog (metric and field
names, descriptions, synonyms, ``ai_context`` instructions) and must answer by
calling one tool that picks existing metrics and fields. The pick is then
validated and compiled by the same code path as any other query, so a made-up
name or an unsafe filter is rejected rather than executed.

Needs ``pip install 'ossie-duck[ai]'`` and ``ANTHROPIC_API_KEY``. The client is
injectable, which is how the tests run without network access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .compiler import QueryRequest
from .engine import Engine, QueryResult
from .errors import QueryError
from .model import SemanticModel

DEFAULT_MODEL_ID = "claude-sonnet-5-5"

TOOL: dict[str, Any] = {
    "name": "semantic_query",
    "description": (
        "Query the semantic model by choosing metrics and dimensions. Use only names "
        "that appear in the catalog in the system prompt."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Metric names exactly as listed, e.g. total_sales or store_sales.total_quantity.",
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fields to group by, written dataset.field.",
            },
            "filters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Boolean conditions over dataset.field, e.g. store.s_state = 'CA'. "
                "Only comparisons, IN, BETWEEN, LIKE, IS NULL, AND/OR/NOT and literals are allowed.",
            },
            "order_by": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "by": {"type": "string", "description": "A selected metric or dimension."},
                        "direction": {"type": "string", "enum": ["asc", "desc"]},
                    },
                    "required": ["by"],
                },
            },
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["metrics"],
    },
}


@dataclass
class AskResult:
    question: str
    request: QueryRequest
    result: QueryResult


def build_system_prompt(model: SemanticModel) -> str:
    lines = [
        "You translate analytics questions into calls of the semantic_query tool.",
        "Pick metrics and dimensions only from the catalog below. Prefer the metric whose "
        "description or synonyms match the question. Window metrics such as running totals "
        "or ranks need the grouping their description asks for.",
        "",
        f"Semantic model: {model.name}" + (f" - {model.description}" if model.description else ""),
    ]
    if model.ai_instructions:
        lines.append(f"Instructions from the model author: {model.ai_instructions}")

    lines += ["", "Metrics:"]
    for m in model.all_metrics():
        extra = f" Also known as: {', '.join(m.synonyms)}." if m.synonyms else ""
        lines.append(f"- {m.ref} ({m.datatype or 'unspecified'}): {m.description}{extra}")

    lines += ["", "Fields (dimensions and filters), written dataset.field:"]
    for ds in model.datasets.values():
        syn = f" (also: {', '.join(ds.synonyms)})" if ds.synonyms else ""
        lines.append(f"{ds.name}: {ds.description}{syn}")
        for f in ds.fields.values():
            tags = ", ".join(t for t in (f.datatype, "time" if f.is_time else None) if t)
            extra = f" Also known as: {', '.join(f.synonyms)}." if f.synonyms else ""
            lines.append(f"  - {ds.name}.{f.name} ({tags or 'unspecified'}): {f.description}{extra}")
    return "\n".join(lines)


def request_from_tool_input(data: dict[str, Any]) -> QueryRequest:
    return QueryRequest.from_dict(data)


def _default_client() -> Any:
    try:
        import anthropic
    except ImportError as exc:
        raise QueryError("`ask` needs the anthropic package: pip install 'ossie-duck[ai]'") from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise QueryError("`ask` needs ANTHROPIC_API_KEY to be set")
    return anthropic.Anthropic()


def ask(
    engine: Engine,
    question: str,
    *,
    client: Any = None,
    model_id: str | None = None,
    max_attempts: int = 2,
) -> AskResult:
    """Answer a question by letting the LLM choose a semantic query, then running it.

    If the chosen query is rejected (unknown name, unsafe filter, DuckDB error) the
    error is sent back once so the model can correct itself.
    """
    client = client if client is not None else _default_client()
    model_id = model_id or os.environ.get("OSSIE_DUCK_MODEL", DEFAULT_MODEL_ID)
    system = build_system_prompt(engine.model)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    last_error: QueryError | None = None

    for _ in range(max_attempts):
        response = client.messages.create(
            model=model_id,
            max_tokens=1024,
            system=system,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL["name"]},
            messages=messages,
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        if block is None:
            raise QueryError("the model did not return a query")
        try:
            request = request_from_tool_input(dict(block.input))
            return AskResult(question, request, engine.query(request))
        except QueryError as exc:
            last_error = exc
            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "is_error": True,
                            "content": str(exc)[:1500],
                        }
                    ],
                }
            )
    assert last_error is not None
    raise last_error
