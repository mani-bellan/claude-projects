"""Read-only queries over the gold marts.

Every function is a pure ``con -> DataFrame`` mapping (mirroring the pipeline's
pure-function style), so panels are unit-testable without Streamlit. Nothing
here writes; the app opens DuckDB with ``read_only=True`` so a running pipeline
pass is never blocked (DuckDB is single-writer).

Note on currency: order amounts are stored per-currency and are *not* additive
across currencies (INR + USD is meaningless). So revenue always keeps
``currency`` as a dimension and the app filters to one currency; order *counts*
are currency-agnostic and safe to aggregate.
"""

from __future__ import annotations

import duckdb
import pandas as pd

# Funnel stage order: the progression, then the two terminal negative states.
FUNNEL_ORDER = ["placed", "confirmed", "shipped", "delivered",
                "cancelled", "refunded"]


def kpi_summary(con: duckdb.DuckDBPyConnection) -> dict:
    """Headline, currency-agnostic KPIs for the page header."""
    orders, customers = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT customer_id)
        FROM silver.orders_current
    """).fetchone()
    batches, avg_qr, last_seen = con.execute("""
        SELECT COUNT(*), AVG(quarantine_rate), MAX(processed_at)
        FROM gold.dq_metrics
    """).fetchone()
    return {
        "total_orders": orders or 0,
        "distinct_customers": customers or 0,
        "batches": batches or 0,
        "avg_quarantine_rate": float(avg_qr or 0.0),
        "last_processed_at": last_seen,
    }


def currencies(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Distinct currencies present in the revenue mart."""
    rows = con.execute(
        "SELECT DISTINCT currency FROM gold.daily_revenue ORDER BY currency"
    ).fetchall()
    return [r[0] for r in rows]


def revenue_by_day(
    con: duckdb.DuckDBPyConnection, currency: str | None = None
) -> pd.DataFrame:
    """Daily revenue + order count, optionally filtered to one currency."""
    sql = """
        SELECT order_date, currency,
               SUM(orders) AS orders,
               SUM(revenue) AS revenue
        FROM gold.daily_revenue
        {where}
        GROUP BY order_date, currency
        ORDER BY order_date, currency
    """
    if currency:
        df = con.execute(
            sql.format(where="WHERE currency = ?"), [currency]
        ).df()
    else:
        df = con.execute(sql.format(where="")).df()
    return df


def order_funnel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Order counts per status, sorted into the funnel sequence."""
    df = con.execute(
        "SELECT status, orders, pct FROM gold.order_funnel"
    ).df()
    df["status"] = pd.Categorical(
        df["status"], categories=FUNNEL_ORDER, ordered=True
    )
    return df.sort_values("status").reset_index(drop=True)


def top_customers(
    con: duckdb.DuckDBPyConnection, currency: str, limit: int = 15
) -> pd.DataFrame:
    """Highest-value customers within one currency.

    Revenue is only comparable inside a single currency, so ranking is always
    currency-scoped (the mart is grained by customer_id + currency).
    """
    return con.execute("""
        SELECT customer_id, currency, total_orders, gross_revenue,
               first_order_ts, last_order_ts
        FROM gold.customer_orders
        WHERE currency = ?
        ORDER BY gross_revenue DESC
        LIMIT ?
    """, [currency, limit]).df()


def customer_stats(con: duckdb.DuckDBPyConnection) -> dict:
    """Repeat-purchase summary, rolled up to the customer (across currencies)."""
    total, repeat = con.execute("""
        WITH per_customer AS (
            SELECT customer_id, SUM(total_orders) AS orders
            FROM gold.customer_orders
            GROUP BY customer_id
        )
        SELECT COUNT(*), COUNT(*) FILTER (WHERE orders > 1)
        FROM per_customer
    """).fetchone()
    return {
        "total_customers": total or 0,
        "repeat_customers": repeat or 0,
        "repeat_rate": (repeat / total) if total else 0.0,
    }


def dq_by_batch(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-batch data-quality metrics in processing order."""
    df = con.execute("""
        SELECT batch_id, processed_at, batch_status,
               bronze_rows, quarantined_rows, quarantine_rate
        FROM gold.dq_metrics
        ORDER BY processed_at
    """).df()
    if not df.empty:
        df["batch_short"] = df["batch_id"].str.slice(0, 8)
    return df
