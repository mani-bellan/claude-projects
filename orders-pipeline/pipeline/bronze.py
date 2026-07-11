"""Bronze layer: drift-proof raw capture, idempotent by batch_id."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb

from pipeline.landing import Batch, LandingError, archive_batch, read_and_verify, record_hash
from pipeline.schema_registry import infer_schema, schema_hash


def is_processed(con: duckdb.DuckDBPyConnection, batch_id: str) -> bool:
    return con.execute(
        "SELECT 1 FROM meta.processed_batches WHERE batch_id = ?", [batch_id]).fetchone() is not None


def load_batch(con: duckdb.DuckDBPyConnection, batch: Batch) -> dict:
    """Load one batch into bronze. Returns {batch_id, rows, skipped}.

    Idempotent: delete-then-insert keyed on batch_id, and the processed-batches
    registry short-circuits redelivered files. The batch is only registered
    after the load commits, so a crash mid-load is healed by the next retry.
    """
    if is_processed(con, batch.batch_id):
        return {"batch_id": batch.batch_id, "rows": 0, "skipped": True}

    records = read_and_verify(batch)  # raises LandingError on corrupt/mismatched files
    s_hash = schema_hash(infer_schema(records))
    now = datetime.now(timezone.utc)

    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM bronze.orders_raw WHERE batch_id = ?", [batch.batch_id])
        if records:
            con.executemany(
                "INSERT INTO bronze.orders_raw VALUES (?, ?, ?, ?, ?, ?)",
                [[batch.batch_id, batch.data_path.name, now, record_hash(r),
                  s_hash, json.dumps(r, ensure_ascii=False)] for r in records])
        con.execute(
            "INSERT INTO meta.processed_batches VALUES (?, ?, ?, ?, 'loaded')",
            [batch.batch_id, batch.data_path.name, len(records), now])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"batch_id": batch.batch_id, "rows": len(records), "skipped": False}


def ingest_incoming(con: duckdb.DuckDBPyConnection, batches: list[Batch],
                    processed_dir, failed_dir) -> list[dict]:
    """Load a set of discovered batches, archiving each as it lands."""
    results = []
    for batch in batches:
        try:
            result = load_batch(con, batch)
            archive_batch(batch, processed_dir)
            results.append(result)
        except LandingError as e:
            now = datetime.now(timezone.utc)
            con.execute(
                "INSERT OR REPLACE INTO meta.processed_batches VALUES (?, ?, 0, ?, 'failed')",
                [batch.batch_id, batch.data_path.name, now])
            archive_batch(batch, failed_dir)
            results.append({"batch_id": batch.batch_id, "rows": 0,
                            "skipped": False, "error": str(e)})
    return results
