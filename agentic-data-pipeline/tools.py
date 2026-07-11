"""DuckDB tools for the data engineering agent."""

import os
import duckdb
from anthropic import beta_tool

# Single shared connection — persists for the process lifetime
_DB_PATH = os.getenv("DUCKDB_PATH", "pipeline.duckdb")
_conn = duckdb.connect(_DB_PATH)


def _fmt_table(result) -> str:
    """Format a DuckDB result as a readable table string."""
    rows = result.fetchmany(50)
    if not rows:
        return "(no rows)"
    cols = [d[0] for d in result.description]
    header = " | ".join(cols)
    sep = "-" * len(header)
    lines = [header, sep] + [" | ".join(str(v) for v in row) for row in rows]
    if len(rows) == 50:
        lines.append("... (showing first 50 rows)")
    else:
        lines.append(f"({len(rows)} rows)")
    return "\n".join(lines)


# ── Ingestion ──────────────────────────────────────────────────────────────────

@beta_tool
def load_file(file_path: str, table_name: str) -> str:
    """Load a data file into DuckDB. Supports CSV, Parquet, and JSON.

    Args:
        file_path: Path to the input file (.csv, .parquet, .json, or .jsonl).
        table_name: Target table name to create in DuckDB (overwritten if it exists).
    """
    ext = os.path.splitext(file_path.strip())[1].lower()
    try:
        if ext == ".csv":
            _conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_csv_auto('{file_path}')"
            )
        elif ext == ".parquet":
            _conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_parquet('{file_path}')"
            )
        elif ext in (".json", ".jsonl"):
            _conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_json_auto('{file_path}')"
            )
        else:
            return f"Unsupported format '{ext}'. Use .csv, .parquet, .json, or .jsonl"

        count = _conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        return f"Loaded {count:,} rows into table '{table_name}' from '{file_path}'"
    except Exception as e:
        return f"Error loading file: {e}"


# ── Schema exploration ─────────────────────────────────────────────────────────

@beta_tool
def list_tables() -> str:
    """List all tables currently available in the DuckDB database."""
    try:
        tables = _conn.execute("SHOW TABLES").fetchall()
        if not tables:
            return "No tables found in the database."
        return "Tables in database:\n" + "\n".join(f"  • {t[0]}" for t in tables)
    except Exception as e:
        return f"Error listing tables: {e}"


@beta_tool
def describe_table(table_name: str) -> str:
    """Show the schema of a table: column names and data types.

    Args:
        table_name: Name of the table to describe.
    """
    try:
        result = _conn.execute(f"DESCRIBE {table_name}")
        rows = result.fetchall()
        cols = [d[0] for d in result.description]
        header = " | ".join(cols[:3])  # column_name | column_type | null
        sep = "-" * len(header)
        lines = [f"Schema for '{table_name}':", header, sep]
        for row in rows:
            lines.append(" | ".join(str(v) for v in row[:3]))
        return "\n".join(lines)
    except Exception as e:
        return f"Error describing table '{table_name}': {e}"


# ── Query execution ────────────────────────────────────────────────────────────

@beta_tool
def run_sql(query: str) -> str:
    """Execute any SQL query against DuckDB and return the results.

    Args:
        query: Valid DuckDB SQL (SELECT, CREATE TABLE AS, INSERT, UPDATE, DELETE, etc.).
    """
    try:
        result = _conn.execute(query)
        if result.description is None:
            return "Query executed successfully (no rows returned)."
        return _fmt_table(result)
    except Exception as e:
        return f"SQL error: {e}"


@beta_tool
def sample_table(table_name: str, n_rows: int = 5) -> str:
    """Preview the first N rows of a table.

    Args:
        table_name: Name of the table to preview.
        n_rows: Number of rows to return (default 5, capped at 20).
    """
    n_rows = min(max(1, n_rows), 20)
    try:
        result = _conn.execute(f"SELECT * FROM {table_name} LIMIT {n_rows}")
        return _fmt_table(result)
    except Exception as e:
        return f"Error sampling '{table_name}': {e}"


# ── Profiling ──────────────────────────────────────────────────────────────────

@beta_tool
def profile_table(table_name: str) -> str:
    """Generate a statistical profile: row count, null rates, distinct counts, and numeric stats.

    Args:
        table_name: Name of the table to profile.
    """
    try:
        row_count = _conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        result = _conn.execute(f"SUMMARIZE {table_name}")
        col_names = [d[0] for d in result.description]
        rows = result.fetchall()

        lines = [f"Profile: '{table_name}'  ({row_count:,} rows)", ""]
        for row in rows:
            d = dict(zip(col_names, row))
            name = d.get("column_name", "?")
            dtype = d.get("column_type", "?")
            null_pct = d.get("null_percentage", 0) or 0
            unique = d.get("approx_unique", "?")

            stat = f"  {name} ({dtype}): nulls={float(null_pct):.1f}%  unique≈{unique}"

            mn = d.get("min")
            mx = d.get("max")
            avg = d.get("avg")
            if mn is not None:
                stat += f"  range=[{mn}, {mx}]"
            if avg is not None:
                try:
                    stat += f"  avg={float(avg):.2f}"
                except (TypeError, ValueError):
                    pass
            lines.append(stat)

        return "\n".join(lines)
    except Exception as e:
        return f"Error profiling '{table_name}': {e}"


# ── Quality checks ─────────────────────────────────────────────────────────────

@beta_tool
def check_duplicates(table_name: str, columns: str = "") -> str:
    """Detect duplicate rows in a table.

    Args:
        table_name: Name of the table to check.
        columns: Comma-separated column names to group by when checking for duplicates.
                 Leave empty to check across all columns.
    """
    try:
        if columns.strip():
            col_list = ", ".join(c.strip() for c in columns.split(","))
            result = _conn.execute(f"""
                SELECT {col_list}, COUNT(*) AS occurrences
                FROM {table_name}
                GROUP BY {col_list}
                HAVING COUNT(*) > 1
                ORDER BY occurrences DESC
                LIMIT 10
            """)
            rows = result.fetchall()
            if not rows:
                return f"No duplicates found on columns ({columns}) in '{table_name}'"
            total = sum(r[-1] for r in rows)
            lines = [f"Found {len(rows)} duplicate groups ({total} extra rows) on ({columns}):"]
            lines += [str(r) for r in rows]
            return "\n".join(lines)
        else:
            schema = _conn.execute(f"DESCRIBE {table_name}").fetchall()
            all_cols = ", ".join(r[0] for r in schema)
            count = _conn.execute(f"""
                SELECT COUNT(*) FROM (
                    SELECT {all_cols}, COUNT(*) AS cnt
                    FROM {table_name}
                    GROUP BY {all_cols}
                    HAVING COUNT(*) > 1
                )
            """).fetchone()[0]
            if count == 0:
                return f"No fully duplicate rows found in '{table_name}'"
            return f"Found {count} duplicate row group(s) in '{table_name}'"
    except Exception as e:
        return f"Error checking duplicates: {e}"


# ── Export ─────────────────────────────────────────────────────────────────────

@beta_tool
def export_table(table_name: str, output_path: str, format: str = "csv") -> str:
    """Export a DuckDB table to a file.

    Args:
        table_name: Name of the table (or a SELECT query wrapped in parentheses) to export.
        output_path: Destination file path (e.g., 'output/results.csv').
        format: Output format — 'csv' or 'parquet'.
    """
    try:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        fmt = format.lower()
        if fmt == "parquet":
            _conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET)")
        else:
            _conn.execute(f"COPY {table_name} TO '{output_path}' (HEADER, DELIMITER ',')")

        count = _conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        return f"Exported {count:,} rows from '{table_name}' → '{output_path}' ({fmt})"
    except Exception as e:
        return f"Error exporting '{table_name}': {e}"
