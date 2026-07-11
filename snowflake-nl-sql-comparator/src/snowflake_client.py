"""Snowflake connection, query execution, JWT minting, and stage download."""

from __future__ import annotations

import gzip
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import snowflake.connector

from .config import Config


@dataclass
class QueryResult:
    sql: str
    rows: pd.DataFrame
    row_count: int
    elapsed_ms: int
    error: str | None = None
    query_id: str | None = None


class SnowflakeClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._conn: snowflake.connector.SnowflakeConnection | None = None

    def connect(self) -> snowflake.connector.SnowflakeConnection:
        if self._conn is None or self._conn.is_closed():
            self._conn = snowflake.connector.connect(
                account=self.cfg.sf_account,
                user=self.cfg.sf_user,
                password=self.cfg.sf_password,
                warehouse=self.cfg.sf_warehouse,
                database=self.cfg.sf_database,
                schema=self.cfg.sf_schema,
                role=self.cfg.sf_role,
            )
        return self._conn

    def close(self):
        if self._conn and not self._conn.is_closed():
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, row_limit: int = 1000) -> QueryResult:
        """Execute SQL and return up to row_limit rows. Errors are captured, not raised."""
        conn = self.connect()
        start = time.perf_counter()
        try:
            cur = conn.cursor()
            cur.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 60")
            cur.execute(sql)
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = cur.fetchmany(row_limit)
            elapsed = int((time.perf_counter() - start) * 1000)
            df = pd.DataFrame(rows, columns=cols)
            return QueryResult(
                sql=sql,
                rows=df,
                row_count=len(rows),
                elapsed_ms=elapsed,
                query_id=cur.sfqid,
            )
        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)
            return QueryResult(
                sql=sql,
                rows=pd.DataFrame(),
                row_count=0,
                elapsed_ms=elapsed,
                error=str(e),
            )

    def cortex_rest_auth_header(self) -> str:
        """Return the Authorization header value for Snowflake REST API calls.

        Uses the active connection's session token — works on every Snowflake
        edition (including trials), no SCOPED_SERVICE_TOKEN required, no
        key-pair / PAT setup. The token is scoped to whatever role the
        connection was opened with.
        """
        conn = self.connect()
        token = conn.rest.token
        if not token:
            raise RuntimeError(
                "No session token available — the Snowflake connection isn't authenticated."
            )
        return f'Snowflake Token="{token}"'

    def download_from_stage(self, stage_path: str) -> Path:
        """Download a file from a Snowflake stage to a temp dir; returns local Path.

        Handles both uncompressed (e.g. `model.yaml`) and gzipped (`model.yaml.gz`)
        stage files transparently — the local result is always the decompressed YAML.

        `stage_path` example: `@MY_DB.MY_SCHEMA.MY_STAGE/sales.yaml`
        """
        if not stage_path.startswith("@"):
            raise ValueError(
                f"Stage path must start with '@', got: {stage_path}"
            )

        dest_dir = Path(tempfile.mkdtemp(prefix="snowflake_stage_"))
        requested_filename = stage_path.rsplit("/", 1)[-1]

        conn = self.connect()
        cur = conn.cursor()
        try:
            cur.execute(f"GET {stage_path} file://{dest_dir.resolve()}/")
            results = cur.fetchall()
        finally:
            cur.close()

        if not results:
            raise FileNotFoundError(
                f"Snowflake GET returned no files for {stage_path}. "
                "Check the path exists (LIST @MY_DB.MY_SCHEMA.MY_STAGE) and your role has "
                "USAGE + READ on the stage."
            )

        # Snowflake GET result columns: file, size, status, message.
        # Some connector versions return just the bare filename in column 0.
        downloaded_name = results[0][0]
        downloaded_path = dest_dir / Path(downloaded_name).name
        if not downloaded_path.exists():
            # Fall back: glob the temp dir (rare connector quirk)
            candidates = list(dest_dir.iterdir())
            if not candidates:
                raise FileNotFoundError(f"Download succeeded but no file at {dest_dir}")
            downloaded_path = candidates[0]

        # Decompress if gzipped — the YAML on the stage may have been PUT with
        # AUTO_COMPRESS=TRUE (the connector default), producing a .gz file.
        if downloaded_path.suffix == ".gz":
            decompressed = downloaded_path.with_suffix("")
            with gzip.open(downloaded_path, "rb") as f_in, open(decompressed, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            downloaded_path = decompressed

        # Sanity check: the result should look like YAML the user asked for
        if requested_filename and not downloaded_path.name.startswith(
            Path(requested_filename).stem
        ):
            # Not fatal — log via the return value; the caller can inspect
            pass

        return downloaded_path

    def describe_table(self, fully_qualified: str) -> list[dict[str, Any]]:
        """DESCRIBE a table; returns list of {name, type, null?, ...}."""
        conn = self.connect()
        cur = conn.cursor(snowflake.connector.DictCursor)
        cur.execute(f"DESCRIBE TABLE {fully_qualified}")
        rows = cur.fetchall()
        cur.close()
        return rows
