"""Unit tests for the viz query layer (pure con -> frame functions).

Builds a real gold warehouse via the pipeline, then reads it back through a
read-only connection — the same access mode the Streamlit app uses.
"""

import duckdb
import pytest

from pipeline.run import run_once
from tests.conftest import valid_order, write_batch_files
from viz import queries, theme


@pytest.fixture
def gold_con(paths):
    """A populated, read-only warehouse: mixed currencies, statuses, 2 batches."""
    write_batch_files(paths.incoming, [
        valid_order(customer_id="CUST-1", currency="INR", total_amount=100.0, status="delivered"),
        valid_order(customer_id="CUST-1", currency="INR", total_amount=200.0, status="placed"),
        valid_order(customer_id="CUST-2", currency="USD", total_amount=50.0, status="shipped"),
    ])
    run_once(paths)
    # a second batch with a bad row so dq_metrics has a non-zero rate
    write_batch_files(paths.incoming,
                      [valid_order(customer_id="CUST-3", currency="EUR")
                       for _ in range(4)]
                      + [valid_order(order_id=None)])
    run_once(paths)
    con = duckdb.connect(str(paths.db_path), read_only=True)
    yield con
    con.close()


def test_kpi_summary_shape(gold_con):
    kpi = queries.kpi_summary(gold_con)
    assert kpi["total_orders"] > 0
    assert kpi["distinct_customers"] >= 3
    assert kpi["batches"] == 2
    assert 0.0 <= kpi["avg_quarantine_rate"] <= 1.0
    assert kpi["last_processed_at"] is not None


def test_currencies_listed(gold_con):
    curr = queries.currencies(gold_con)
    assert {"INR", "USD"} <= set(curr)


def test_revenue_by_day_filter(gold_con):
    all_rows = queries.revenue_by_day(gold_con)
    assert set(all_rows.columns) == {"order_date", "currency", "orders", "revenue"}
    inr = queries.revenue_by_day(gold_con, currency="INR")
    assert (inr["currency"] == "INR").all()
    assert inr["revenue"].sum() == 300.0  # 100 + 200, currency-isolated


def test_order_funnel_is_sorted_into_stage_order(gold_con):
    df = queries.order_funnel(gold_con)
    present = [s for s in queries.FUNNEL_ORDER if s in set(df["status"].astype(str))]
    assert list(df["status"].astype(str)) == present
    assert abs(df["pct"].sum() - 100.0) < 0.5


def test_top_customers_is_currency_scoped_and_ranked(gold_con):
    inr = queries.top_customers(gold_con, currency="INR", limit=2)
    assert len(inr) <= 2
    assert (inr["currency"] == "INR").all()
    assert inr["gross_revenue"].is_monotonic_decreasing
    # CUST-1's two INR orders (100 + 200) roll into one currency-scoped row
    cust1 = inr[inr["customer_id"] == "CUST-1"]
    assert cust1["gross_revenue"].iloc[0] == 300.0
    assert cust1["total_orders"].iloc[0] == 2


def test_customer_stats_repeat_rate_rolls_up_across_currencies(gold_con):
    stats = queries.customer_stats(gold_con)
    assert stats["total_customers"] >= 3
    assert stats["repeat_customers"] >= 1  # CUST-1 ordered twice (both INR)
    assert 0.0 <= stats["repeat_rate"] <= 1.0


def test_dq_by_batch_has_short_id_and_rate(gold_con):
    df = queries.dq_by_batch(gold_con)
    assert len(df) == 2
    assert df["batch_short"].str.len().max() <= 8
    assert (df["quarantine_rate"] >= 0).all()


def test_read_only_connection_cannot_write(gold_con):
    with pytest.raises(duckdb.Error):
        gold_con.execute("CREATE TABLE gold.should_fail (x INT)")


def test_currency_palette_covers_present_currencies(gold_con):
    # Every currency in the data must have a fixed hue slot (no cycling).
    for c in queries.currencies(gold_con):
        assert c in theme.CURRENCY_ORDER, f"{c} has no assigned color slot"
