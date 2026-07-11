"""Claude NL→SQL runner: agentic loop with execute_snowflake_sql tool + prompt caching."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .snowflake_client import QueryResult, SnowflakeClient

MODEL = "claude-sonnet-4-6"
MAX_TURNS = 6  # cap the tool-use loop
MAX_TOKENS = 4096

TOOLS = [
    {
        "name": "execute_snowflake_sql",
        "description": (
            "Execute a Snowflake SQL query and return the first 1000 rows. "
            "Returns rows as JSON, the column list, the row count, and any error message. "
            "Use this to test your query — if it errors, read the error and try again."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The Snowflake SQL query to execute. Must be a single SELECT.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "describe_table",
        "description": (
            "Get column names and types for a Snowflake table. Use this only when the "
            "semantic model is ambiguous about a column — it costs a round trip."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Fully-qualified table name: DATABASE.SCHEMA.TABLE",
                },
            },
            "required": ["table"],
        },
    },
]


@dataclass
class ClaudeRunResult:
    question: str
    final_sql: str | None
    final_result: QueryResult | None
    explanation: str
    turns: int
    elapsed_ms: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    history: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class ClaudeRunner:
    def __init__(self, api_key: str, system_prompt: str, sf: SnowflakeClient):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = system_prompt
        self.sf = sf

    def _dispatch_tool(self, name: str, args: dict[str, Any]) -> tuple[str, QueryResult | None]:
        if name == "execute_snowflake_sql":
            sql = args.get("sql", "")
            result = self.sf.execute(sql)
            if result.error:
                content = f"ERROR: {result.error}"
            else:
                # Return columns + first 20 rows as compact JSON for the model
                preview = result.rows.head(20).to_dict(orient="records")
                content = (
                    f"OK — {result.row_count} rows returned in {result.elapsed_ms}ms.\n"
                    f"Columns: {list(result.rows.columns)}\n"
                    f"First {min(20, result.row_count)} rows: {preview}"
                )
            return content, result

        if name == "describe_table":
            table = args.get("table", "")
            try:
                cols = self.sf.describe_table(table)
                summary = [{"name": c["name"], "type": c["type"]} for c in cols]
                return f"Columns for {table}: {summary}", None
            except Exception as e:
                return f"ERROR describing {table}: {e}", None

        return f"Unknown tool: {name}", None

    def ask(self, question: str) -> ClaudeRunResult:
        start = time.perf_counter()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": question},
        ]
        final_sql: str | None = None
        final_result: QueryResult | None = None
        explanation = ""
        in_tokens = out_tokens = cache_read = cache_create = 0

        for turn in range(MAX_TURNS):
            try:
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=[
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=TOOLS,
                    messages=messages,
                )
            except anthropic.APIError as e:
                return ClaudeRunResult(
                    question=question,
                    final_sql=final_sql,
                    final_result=final_result,
                    explanation="",
                    turns=turn,
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    cache_read_tokens=cache_read,
                    cache_creation_tokens=cache_create,
                    history=messages,
                    error=f"Anthropic API error: {e}",
                )

            in_tokens += response.usage.input_tokens
            out_tokens += response.usage.output_tokens
            cache_read += getattr(response.usage, "cache_read_input_tokens", 0) or 0
            cache_create += getattr(response.usage, "cache_creation_input_tokens", 0) or 0

            # Collect text blocks for explanation
            text_blocks = [b.text for b in response.content if b.type == "text"]
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            # Append assistant turn
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn" or not tool_uses:
                explanation = "\n\n".join(text_blocks).strip()
                break

            # Execute each tool call and append results
            tool_results = []
            for tu in tool_uses:
                content, result = self._dispatch_tool(tu.name, tu.input)
                if tu.name == "execute_snowflake_sql" and result is not None:
                    if not result.error:
                        # Latest successful SQL wins
                        final_sql = tu.input.get("sql")
                        final_result = result
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": content,
                        "is_error": result is not None and result.error is not None,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        elapsed = int((time.perf_counter() - start) * 1000)
        return ClaudeRunResult(
            question=question,
            final_sql=final_sql,
            final_result=final_result,
            explanation=explanation,
            turns=turn + 1,
            elapsed_ms=elapsed,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_create,
            history=messages,
        )
