"""Persist comparison runs to a Snowflake table — your accumulating eval dataset."""

from __future__ import annotations


from .claude_runner import ClaudeRunResult
from .comparator import Comparison
from .config import Config
from .cortex_runner import CortexAnalystResult
from .snowflake_client import SnowflakeClient


def ensure_table(sf: SnowflakeClient, cfg: Config):
    """Create the run log table if missing."""
    conn = sf.connect()
    cur = conn.cursor()
    table = f"{cfg.sf_database}.{cfg.sf_schema}.{cfg.run_log_table}"
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            run_id              STRING DEFAULT UUID_STRING(),
            asked_at            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            question            STRING,
            claude_sql          STRING,
            claude_row_count    NUMBER,
            claude_elapsed_ms   NUMBER,
            claude_input_tokens NUMBER,
            claude_output_tokens NUMBER,
            claude_cache_read   NUMBER,
            claude_error        STRING,
            cortex_sql          STRING,
            cortex_row_count    NUMBER,
            cortex_elapsed_ms   NUMBER,
            cortex_error        STRING,
            rows_match          BOOLEAN,
            columns_match       BOOLEAN,
            comparison_detail   STRING,
            user_feedback       STRING
        )
        """
    )
    cur.close()


def log_run(
    sf: SnowflakeClient,
    cfg: Config,
    question: str,
    claude: ClaudeRunResult,
    cortex: CortexAnalystResult,
    comparison: Comparison,
    user_feedback: str | None = None,
) -> str:
    """Insert one comparison row. Returns the run_id."""
    conn = sf.connect()
    cur = conn.cursor()
    table = f"{cfg.sf_database}.{cfg.sf_schema}.{cfg.run_log_table}"
    cur.execute(
        f"""
        INSERT INTO {table} (
            question, claude_sql, claude_row_count, claude_elapsed_ms,
            claude_input_tokens, claude_output_tokens, claude_cache_read, claude_error,
            cortex_sql, cortex_row_count, cortex_elapsed_ms, cortex_error,
            rows_match, columns_match, comparison_detail, user_feedback
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            question,
            claude.final_sql,
            claude.final_result.row_count if claude.final_result else 0,
            claude.elapsed_ms,
            claude.input_tokens,
            claude.output_tokens,
            claude.cache_read_tokens,
            claude.error,
            cortex.final_sql,
            cortex.final_result.row_count if cortex.final_result else 0,
            cortex.elapsed_ms,
            cortex.error,
            comparison.rows_match,
            comparison.columns_match,
            comparison.detail,
            user_feedback,
        ),
    )
    cur.execute("SELECT LAST_QUERY_ID()")
    qid = cur.fetchone()[0]
    cur.close()
    return qid
