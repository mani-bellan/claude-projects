"""Agentic data engineering pipeline powered by Claude + DuckDB."""

import os
import sys
import anthropic
from dotenv import load_dotenv

from tools import (
    load_file,
    list_tables,
    describe_table,
    run_sql,
    sample_table,
    profile_table,
    check_duplicates,
    export_table,
)

load_dotenv()

SYSTEM_PROMPT = """\
You are a data engineering agent with direct access to a DuckDB database.

Your capabilities:
  load_file      — ingest CSV, Parquet, or JSON files into tables
  list_tables    — see what tables exist
  describe_table — inspect schema and column types
  run_sql        — execute any SQL (transforms, aggregations, joins)
  sample_table   — preview rows
  profile_table  — statistical summary (nulls, ranges, averages)
  check_duplicates — find duplicate rows
  export_table   — write results to CSV or Parquet

Workflow guidelines:
1. Always start by understanding what data is available.
2. Profile before transforming — know your nulls and distributions first.
3. Verify row counts after every major operation.
4. Be concise: show key numbers, not raw dumps.
5. When writing SQL transforms, store results as new tables, then export.
"""

ALL_TOOLS = [
    load_file,
    list_tables,
    describe_table,
    run_sql,
    sample_table,
    profile_table,
    check_duplicates,
    export_table,
]


def run_pipeline(task: str) -> None:
    """Run the data engineering agent for the given task."""
    client = anthropic.Anthropic()

    print(f"\n{'═' * 64}")
    print(f"  Task: {task}")
    print(f"{'═' * 64}\n")

    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[{"role": "user", "content": task}],
    )

    step = 0
    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                step += 1
                print(f"[{step}] {block.text.strip()}\n")

    print(f"{'═' * 64}")
    print("  Pipeline complete.")
    print(f"{'═' * 64}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

DEFAULT_TASK = (
    "Load data/sample_sales.csv into a table called 'sales'. "
    "Profile it and check for duplicates. "
    "Then find revenue by product (top 5) and by region. "
    "Save the top-products result to output/top_products.csv "
    "and the regional summary to output/regional_summary.csv."
)

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]).strip() or DEFAULT_TASK
    run_pipeline(task)
