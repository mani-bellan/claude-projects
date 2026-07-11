"""Load a Snowflake semantic-model YAML and render it as a Claude system-prompt block.

Parsing is fail-soft. pyyaml (YAML 1.1) trips on some Cortex Analyst YAML constructs
that the more permissive ruamel.yaml (YAML 1.2) handles. If both fail, we still keep
the raw text for Claude — only the parsed-structure features (verified queries,
table names) become unavailable.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML


@dataclass
class SemanticModel:
    name: str
    description: str
    raw_yaml: str
    parsed: dict[str, Any] = field(default_factory=dict)
    tables: list[dict[str, Any]] = field(default_factory=list)
    parse_error: str | None = None


def _parse(text: str) -> tuple[dict[str, Any], str | None]:
    """Try pyyaml first, then ruamel.yaml. Return (parsed_dict, error_or_None)."""
    # First attempt: pyyaml (fastest, handles 95% of cases)
    pyyaml_err: str | None = None
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data, None
        if data is not None:
            pyyaml_err = f"top-level not a mapping (got {type(data).__name__})"
    except yaml.YAMLError as e:
        pyyaml_err = f"{type(e).__name__}: {e}"

    # Second attempt: ruamel.yaml (YAML 1.2, more lenient with Cortex Analyst quirks)
    try:
        ryaml = YAML(typ="safe", pure=True)
        data = ryaml.load(io.StringIO(text))
        if isinstance(data, dict):
            return data, None
        if data is not None:
            return {}, f"top-level not a mapping (got {type(data).__name__})"
        return {}, "empty document"
    except Exception as e:
        ruamel_err = f"{type(e).__name__}: {e}"

    return {}, f"pyyaml: {pyyaml_err}; ruamel: {ruamel_err}"


def load(yaml_path: Path) -> SemanticModel:
    text = yaml_path.read_text()
    parsed, parse_error = _parse(text)

    name = parsed.get("name") or yaml_path.stem
    description = parsed.get("description") or ""
    tables = parsed.get("tables") or []
    if not isinstance(tables, list):
        tables = []

    return SemanticModel(
        name=str(name),
        description=str(description),
        raw_yaml=text,
        parsed=parsed,
        tables=tables,
        parse_error=parse_error,
    )


def verified_queries(model: SemanticModel) -> list[dict[str, Any]]:
    """Extract verified queries from the semantic model.

    Cortex Analyst supports verified_queries at the top level. Older / variant
    semantic models nest them under each table. We collect from both.

    Returns a list of dicts; each has at least 'question' and possibly 'name'
    and 'sql'. Returns [] if the YAML failed to parse or no queries are defined.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add_from(block: Any) -> None:
        if not isinstance(block, list):
            return
        for q in block:
            if not isinstance(q, dict):
                continue
            question = q.get("question")
            if not question or not isinstance(question, str):
                continue
            if question in seen:
                continue
            seen.add(question)
            out.append(q)

    _add_from(model.parsed.get("verified_queries"))
    for table in model.tables:
        if isinstance(table, dict):
            _add_from(table.get("verified_queries"))

    return out


def to_system_prompt(model: SemanticModel, physical_schema: bool = False) -> str:
    """Render the semantic model as a system-prompt block.

    We embed the raw YAML rather than re-summarizing — Claude reads YAML natively
    and the cached prefix means we pay this once per session.

    physical_schema=True is for introspected models: column names are real warehouse
    columns (no logical-alias expansion), and the YAML carries sample_values/row_count
    instead of dimensions/measures.
    """
    if physical_schema:
        intro = [
            "You have access to the following schema (YAML), introspected directly from the",
            "warehouse. Column names are physical — use them as-is. `sample_values` show real",
            "data from each column and `row_count` indicates table size; use both to pick the",
            "right tables, joins, and filter literals. Always emit fully-qualified SQL:",
            "DATABASE.SCHEMA.TABLE.",
        ]
    else:
        intro = [
            "You have access to the following semantic model (YAML). Treat dimension/measure names",
            "as logical aliases — when generating SQL, expand them to the underlying `expr` column on",
            "the `base_table`. Always emit fully-qualified SQL: DATABASE.SCHEMA.TABLE.",
        ]
    lines = [
        "You are a Snowflake SQL expert helping users query a data warehouse via natural language.",
        "",
        *intro,
        "",
        "## Snowflake SQL conventions",
        "",
        "- Use `DATE_TRUNC('quarter', col)` for quarter grouping, not `EXTRACT(QUARTER ...)`.",
        "- Use `QUALIFY` for window-function filtering when applicable.",
        "- Wrap measures in their `default_aggregation` (SUM, AVG, COUNT_DISTINCT).",
        "- Always include `LIMIT 1000` on the final SELECT unless the user asks for a single",
        "  aggregate value — this app caps result rows at 1000.",
        "- Prefer ANSI joins (`JOIN ... ON`) over comma joins.",
        "- For 'last quarter' / 'last month' use `DATEADD` against `CURRENT_DATE`.",
        "",
        "## Workflow",
        "",
        "1. Read the user's question and decide which tables and columns from the semantic model apply.",
        "2. Generate a Snowflake SQL query.",
        "3. Call the `execute_snowflake_sql` tool to run it.",
        "4. If the query errors, read the error and self-correct (up to 2 retries).",
        "5. Once you have results, give the user a 1-2 sentence plain-English answer.",
        "",
        "## Semantic model",
        "",
        "```yaml",
        model.raw_yaml.rstrip(),
        "```",
    ]
    return "\n".join(lines)


def list_tables(model: SemanticModel) -> list[str]:
    """Return fully-qualified table names referenced in the semantic model."""
    out = []
    for t in model.tables:
        bt = t.get("base_table", {})
        if all(k in bt for k in ("database", "schema", "table")):
            out.append(f"{bt['database']}.{bt['schema']}.{bt['table']}")
    return out
