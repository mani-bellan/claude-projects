"""DuckDB warehouse: connection helpers and DDL for all layers."""

from __future__ import annotations

from pathlib import Path

import duckdb

DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS bronze.orders_raw (
    batch_id      VARCHAR NOT NULL,
    source_file   VARCHAR NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL,
    record_hash   VARCHAR NOT NULL,
    schema_hash   VARCHAR NOT NULL,
    raw           JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS meta.processed_batches (
    batch_id      VARCHAR PRIMARY KEY,
    source_file   VARCHAR NOT NULL,
    row_count     BIGINT NOT NULL,
    processed_at  TIMESTAMPTZ NOT NULL,
    status        VARCHAR NOT NULL  -- loaded | promoted | quarantined | failed
);

CREATE TABLE IF NOT EXISTS meta.schema_registry (
    schema_hash    VARCHAR NOT NULL,
    schema_json    JSON NOT NULL,
    first_seen_at  TIMESTAMPTZ NOT NULL,
    first_batch_id VARCHAR NOT NULL,
    classification VARCHAR NOT NULL,  -- baseline | additive | column_removed | type_change | unknown
    changes        JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS meta.column_aliases (
    alias_name     VARCHAR PRIMARY KEY,   -- drifted name, e.g. cust_id
    canonical_name VARCHAR NOT NULL       -- e.g. customer_id
);

CREATE TABLE IF NOT EXISTS meta.dq_results (
    batch_id     VARCHAR NOT NULL,
    layer        VARCHAR NOT NULL,
    rule_name    VARCHAR NOT NULL,
    severity     VARCHAR NOT NULL,
    passed       BOOLEAN NOT NULL,
    failed_count BIGINT NOT NULL,
    total_count  BIGINT NOT NULL,
    detail       VARCHAR,
    checked_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.orders_events (
    batch_id      VARCHAR NOT NULL,
    record_hash   VARCHAR NOT NULL,
    order_id      VARCHAR NOT NULL,
    customer_id   VARCHAR,
    customer_name VARCHAR,
    order_ts      TIMESTAMPTZ NOT NULL,
    status        VARCHAR NOT NULL,
    currency      VARCHAR,
    total_amount  DOUBLE,
    items         JSON,
    extras        JSON,          -- additive-drift columns land here
    promoted_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.orders_current (
    order_id      VARCHAR PRIMARY KEY,
    customer_id   VARCHAR,
    customer_name VARCHAR,
    order_ts      TIMESTAMPTZ NOT NULL,
    status        VARCHAR NOT NULL,
    currency      VARCHAR,
    total_amount  DOUBLE,
    items         JSON,
    extras        JSON,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.quarantine (
    batch_id       VARCHAR NOT NULL,
    record_hash    VARCHAR NOT NULL,
    failed_rules   JSON NOT NULL,
    raw            JSON NOT NULL,
    quarantined_at TIMESTAMPTZ NOT NULL
);
"""


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open (and initialize) the warehouse."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(DDL)
    return con
