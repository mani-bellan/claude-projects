"""Orders-pipeline dashboard — a read-only view over the gold marts.

Run:  .venv/bin/streamlit run viz/app.py

Opens ``warehouse/orders.duckdb`` read-only so it never contends with a running
pipeline pass. Charts follow the data-viz skill's validated palette (see
``viz/theme.py``): a legend/direct labels are always present as the secondary
encoding, so identity is never carried by color alone.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Streamlit puts this file's folder (viz/) on sys.path, not the project root,
# so make the root importable before the `viz` package import below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import duckdb  # noqa: E402
import streamlit as st  # noqa: E402

from viz import queries, theme  # noqa: E402

DB_PATH = Path(
    os.environ.get(
        "ORDERS_DB",
        Path(__file__).resolve().parent.parent / "warehouse" / "orders.duckdb",
    )
)
HALT_THRESHOLD = 0.20  # batch halts above this quarantine rate (see README)


@st.cache_resource
def _connect(path: str) -> duckdb.DuckDBPyConnection:
    # read_only => the pipeline (single writer) is never blocked by the viewer.
    return duckdb.connect(path, read_only=True)


@st.cache_data(ttl=60)
def _load(path: str, mtime: float):
    """Pull every panel's frame once per 60s (or when the DB file changes)."""
    con = _connect(path)
    return {
        "kpi": queries.kpi_summary(con),
        "customers_stats": queries.customer_stats(con),
        "currencies": queries.currencies(con),
        "revenue": queries.revenue_by_day(con),
        "funnel": queries.order_funnel(con),
        "dq": queries.dq_by_batch(con),
    }


@st.cache_data(ttl=60)
def _top_customers(path: str, mtime: float, currency: str):
    return queries.top_customers(_connect(path), currency)


def _revenue_chart(df, currency_sel: str, dark: bool):
    df = df[df["currency"] == currency_sel] if currency_sel != "All" else df
    base = alt.Chart(df).encode(
        x=alt.X("order_date:T", title="Order date"),
        y=alt.Y("revenue:Q", title="Revenue"),
    )
    tip = [
        alt.Tooltip("order_date:T", title="Date"),
        alt.Tooltip("currency:N", title="Currency"),
        alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
        alt.Tooltip("orders:Q", title="Orders"),
    ]
    if currency_sel == "All":
        color = alt.Color(
            "currency:N", scale=theme.currency_scale(dark),
            sort=theme.CURRENCY_ORDER, title="Currency",
        )
        line = base.mark_line(strokeWidth=2, point=True).encode(color=color, tooltip=tip)
        return line
    # Single currency: one series, no legend — the title names it.
    area = base.mark_area(opacity=0.15, color=theme.accent(dark))
    line = base.mark_line(
        strokeWidth=2, point=True, color=theme.accent(dark)
    ).encode(tooltip=tip)
    return area + line


def _funnel_chart(df, dark: bool):
    df = df.copy()
    df["status"] = df["status"].astype(str)
    df["label"] = df["orders"].astype(str) + "  (" + df["pct"].round(1).astype(str) + "%)"
    base = alt.Chart(df).encode(
        y=alt.Y("status:N", sort=queries.FUNNEL_ORDER, title=None),
        x=alt.X("orders:Q", title="Orders"),
    )
    bars = base.mark_bar(
        color=theme.accent(dark), cornerRadiusEnd=4, height=22
    ).encode(tooltip=[
        alt.Tooltip("status:N", title="Status"),
        alt.Tooltip("orders:Q", title="Orders"),
        alt.Tooltip("pct:Q", title="Share", format=".1f"),
    ])
    labels = base.mark_text(
        align="left", dx=4, color=theme._INK[dark]["secondary"], fontSize=11
    ).encode(text="label:N")
    return bars + labels


def _top_customers_chart(df, dark: bool):
    base = alt.Chart(df).encode(
        y=alt.Y("customer_id:N", sort="-x", title=None),
        x=alt.X("gross_revenue:Q", title="Gross revenue"),
    )
    return base.mark_bar(
        color=theme.accent(dark), cornerRadiusEnd=4
    ).encode(tooltip=[
        alt.Tooltip("customer_id:N", title="Customer"),
        alt.Tooltip("currency:N", title="Currency"),
        alt.Tooltip("gross_revenue:Q", title="Gross revenue", format=",.0f"),
        alt.Tooltip("total_orders:Q", title="Orders"),
    ])


def _dq_chart(df, dark: bool):
    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("batch_short:N", sort=None, title="Batch (processing order)"),
        y=alt.Y("quarantine_rate:Q", title="Quarantine rate",
                axis=alt.Axis(format="%")),
        color=alt.Color("batch_status:N", scale=theme.status_scale(),
                        title="Batch status"),
        tooltip=[
            alt.Tooltip("batch_id:N", title="Batch"),
            alt.Tooltip("batch_status:N", title="Status"),
            alt.Tooltip("bronze_rows:Q", title="Rows"),
            alt.Tooltip("quarantined_rows:Q", title="Quarantined"),
            alt.Tooltip("quarantine_rate:Q", title="Rate", format=".1%"),
        ],
    )
    rule = alt.Chart(df).mark_rule(
        strokeDash=[4, 4], color=theme.STATUS_COLORS["halted"]
    ).encode(y=alt.datum(HALT_THRESHOLD))
    return bars + rule


def main() -> None:
    st.set_page_config(page_title="Orders pipeline", layout="wide", page_icon="📦")

    if not DB_PATH.exists():
        st.error(f"Warehouse not found at {DB_PATH}. Run the pipeline first: "
                 "`.venv/bin/python -m pipeline.run`")
        st.stop()

    with st.sidebar:
        st.header("Orders pipeline")
        dark = st.toggle("Dark charts", value=True)
        if st.button("↻ Refresh", use_container_width=True):
            _load.clear()
        st.caption(f"Source: `{DB_PATH.name}` (read-only)")

    theme.apply_theme(dark)
    data = _load(str(DB_PATH), DB_PATH.stat().st_mtime)

    kpi, cust = data["kpi"], data["customers_stats"]
    st.title("Orders — pipeline dashboard")
    last = kpi["last_processed_at"]
    st.caption(f"Last batch processed: {last:%Y-%m-%d %H:%M} " if last else "No batches yet")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total orders", f"{kpi['total_orders']:,}")
    c2.metric("Customers", f"{kpi['distinct_customers']:,}")
    c3.metric("Repeat rate", f"{cust['repeat_rate']:.0%}")
    c4.metric("Batches", f"{kpi['batches']:,}")
    c5.metric("Avg quarantine", f"{kpi['avg_quarantine_rate']:.1%}")

    st.divider()

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Revenue over time")
        curr_opts = ["All"] + [c for c in theme.CURRENCY_ORDER if c in data["currencies"]]
        sel = st.selectbox("Currency", curr_opts, index=min(1, len(curr_opts) - 1),
                           help="Amounts aren't additive across currencies — pick one.")
        st.altair_chart(
            _revenue_chart(data["revenue"], sel, dark).properties(height=280),
            use_container_width=True,
        )
    with right:
        st.subheader("Order funnel")
        st.altair_chart(
            _funnel_chart(data["funnel"], dark).properties(height=280),
            use_container_width=True,
        )

    st.divider()

    left2, right2 = st.columns(2)
    with left2:
        st.subheader("Top customers")
        cust_curr = [c for c in theme.CURRENCY_ORDER if c in data["currencies"]]
        tc_sel = st.selectbox(
            "Currency", cust_curr, key="cust_currency",
            help="Revenue ranks within one currency (amounts aren't comparable across).",
        )
        tc = _top_customers(str(DB_PATH), DB_PATH.stat().st_mtime, tc_sel)
        st.altair_chart(
            _top_customers_chart(tc, dark).properties(height=300),
            use_container_width=True,
        )
    with right2:
        st.subheader("Data quality by batch")
        dq = data["dq"]
        if dq.empty:
            st.info("No batches processed yet.")
        else:
            worst = dq.loc[dq["quarantine_rate"].idxmax()]
            if worst["quarantine_rate"] >= HALT_THRESHOLD:
                st.warning(
                    f"{theme.STATUS_ICONS['halted']} Batch "
                    f"{worst['batch_short']} exceeded the "
                    f"{HALT_THRESHOLD:.0%} halt threshold "
                    f"({worst['quarantine_rate']:.1%})."
                )
            st.altair_chart(
                _dq_chart(dq, dark).properties(height=300),
                use_container_width=True,
            )
            with st.expander("Batch detail (table view)"):
                st.dataframe(
                    dq[["batch_short", "batch_status", "bronze_rows",
                        "quarantined_rows", "quarantine_rate"]],
                    use_container_width=True, hide_index=True,
                )


if __name__ == "__main__":
    main()
