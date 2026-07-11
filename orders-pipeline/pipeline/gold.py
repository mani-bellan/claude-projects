"""Gold layer: business marts, rebuilt from silver (pure functions -> idempotent)."""

from __future__ import annotations

import duckdb

MARTS = {
    "daily_revenue": """
        CREATE OR REPLACE TABLE gold.daily_revenue AS
        SELECT CAST(order_ts AS DATE) AS order_date,
               currency,
               status,
               COUNT(*) AS orders,
               ROUND(SUM(total_amount), 2) AS revenue
        FROM silver.orders_current
        WHERE total_amount IS NOT NULL
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """,
    "customer_orders": """
        CREATE OR REPLACE TABLE gold.customer_orders AS
        SELECT customer_id,
               currency,
               COUNT(*) AS total_orders,
               ROUND(SUM(CASE WHEN status != 'refunded' THEN total_amount ELSE 0 END), 2)
                   AS gross_revenue,
               MIN(order_ts) AS first_order_ts,
               MAX(order_ts) AS last_order_ts
        FROM silver.orders_current
        WHERE customer_id IS NOT NULL
        GROUP BY 1, 2
    """,
    "order_funnel": """
        CREATE OR REPLACE TABLE gold.order_funnel AS
        SELECT status, COUNT(*) AS orders,
               ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
        FROM silver.orders_current
        GROUP BY 1
        ORDER BY orders DESC
    """,
    "dq_metrics": """
        CREATE OR REPLACE TABLE gold.dq_metrics AS
        SELECT b.batch_id,
               b.processed_at,
               b.status AS batch_status,
               b.row_count AS bronze_rows,
               COALESCE(q.quarantined, 0) AS quarantined_rows,
               ROUND(COALESCE(q.quarantined, 0) * 1.0 / NULLIF(b.row_count, 0), 4)
                   AS quarantine_rate
        FROM meta.processed_batches b
        LEFT JOIN (
            SELECT batch_id, COUNT(*) AS quarantined
            FROM silver.quarantine GROUP BY 1
        ) q USING (batch_id)
        ORDER BY b.processed_at
    """,
}


def build_all(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Rebuild every mart. Returns mart -> row count."""
    counts = {}
    for name, sql in MARTS.items():
        con.execute(sql)
        counts[name] = con.execute(f"SELECT COUNT(*) FROM gold.{name}").fetchone()[0]
    return counts
