"""End-to-end: semantic queries on DuckDB, checked against hand-written SQL."""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from ossie_duck import Engine, QueryError, QueryRequest


def oracle(con, sql):
    return con.execute(sql).fetchall()


def test_metric_by_dimension_matches_plain_sql(engine, con):
    got = engine.query(QueryRequest(metrics=["total_sales"], dimensions=["date_dim.d_year"])).rows
    want = oracle(con, """
        SELECT d.d_year, SUM(s.ss_ext_sales_price)
        FROM store_sales s JOIN date_dim d ON s.ss_sold_date_sk = d.d_date_sk
        GROUP BY 1 ORDER BY 1""")
    assert got == want and len(got) == 2


def test_two_joins_and_a_filter(engine, con):
    got = engine.query(
        QueryRequest(
            metrics=["total_sales", "total_profit"],
            dimensions=["item.i_category", "date_dim.d_year"],
            filters=["store.s_state = 'CA'", "date_dim.d_year = 2024"],
        )
    )
    want = oracle(con, """
        SELECT i.i_category, d.d_year, SUM(s.ss_ext_sales_price), SUM(s.ss_net_profit)
        FROM store_sales s
        JOIN item i ON s.ss_item_sk = i.i_item_sk
        JOIN date_dim d ON s.ss_sold_date_sk = d.d_date_sk
        JOIN store st ON s.ss_store_sk = st.s_store_sk
        WHERE st.s_state = 'CA' AND d.d_year = 2024
        GROUP BY i.i_category, d.d_year ORDER BY i.i_category, d.d_year""")
    # output order is dimensions in request order: category, year
    assert got.columns == ["i_category", "d_year", "total_sales", "total_profit"]
    assert got.rows == want and len(want) == 5


def test_dataset_scoped_metric(engine, con):
    got = engine.query(QueryRequest(metrics=["store_sales.total_quantity"]))
    assert got.columns == ["total_quantity"]
    assert got.rows == oracle(con, "SELECT SUM(ss_quantity) FROM store_sales")
    # a bare name works while it is unambiguous
    assert engine.query(QueryRequest(metrics=["total_quantity"])).rows == got.rows


def test_computed_field_is_expanded(engine, con):
    got = engine.query(
        QueryRequest(metrics=["total_sales"], dimensions=["customer.customer_full_name"], order_by=[("total_sales", "desc")], limit=3)
    )
    want = oracle(con, """
        SELECT c.c_first_name || ' ' || c.c_last_name AS n, SUM(s.ss_ext_sales_price) AS t
        FROM store_sales s JOIN customer c ON s.ss_customer_sk = c.c_customer_sk
        GROUP BY 1 ORDER BY t DESC LIMIT 3""")
    assert [r[0] for r in got.rows] == [r[0] for r in want]
    assert [r[1] for r in got.rows] == [r[1] for r in want]


def test_cross_dataset_ratio_metric(engine, con):
    got = engine.query(QueryRequest(metrics=["customer_lifetime_value"]))
    (total, n_customers), = oracle(con, """
        SELECT SUM(s.ss_ext_sales_price), COUNT(DISTINCT c.c_customer_sk)
        FROM store_sales s JOIN customer c ON s.ss_customer_sk = c.c_customer_sk""")
    assert float(got.rows[0][0]) == pytest.approx(float(total) / n_customers)


def test_running_total_window_metric(engine, con):
    got = engine.query(QueryRequest(metrics=["cumulative_sales"], dimensions=["date_dim.d_date"]))
    (grand_total,), = oracle(con, "SELECT SUM(ss_ext_sales_price) FROM store_sales")
    assert got.rows[-1][1] == grand_total  # the last day's running total is everything
    values = [r[1] for r in got.rows]
    assert values == sorted(values)  # non-decreasing, so sales are never negative


def test_lag_window_metric(engine, con):
    got = engine.query(
        QueryRequest(metrics=["total_sales", "monthly_sales_change"], dimensions=["date_dim.d_year", "date_dim.d_moy"])
    )
    assert got.rows[0][3] is None  # no previous month
    assert got.rows[1][3] == got.rows[1][2] - got.rows[0][2]
    assert len(got.rows) == 24


def test_rank_window_metric(engine):
    got = engine.query(
        QueryRequest(metrics=["brand_rank_in_store"], dimensions=["store.s_store_sk", "item.i_brand"])
    )
    by_store: dict[int, list[int]] = {}
    for store, _brand, rank in got.rows:
        by_store.setdefault(store, []).append(rank)
    assert len(by_store) == 6
    assert all(min(ranks) == 1 for ranks in by_store.values())


def test_left_join_keeps_facts_without_a_matching_dimension_row(engine, con):
    con.execute("""INSERT INTO store_sales
        SELECT ss_sold_date_sk, ss_item_sk, 999999, 999999, ss_store_sk, ss_quantity, ss_sales_price,
               ss_ext_sales_price, ss_net_profit FROM store_sales LIMIT 1""")  # customer 999999 does not exist
    got = engine.query(QueryRequest(metrics=["total_sales"], dimensions=["customer.c_last_name"]))
    (grand_total,), = oracle(con, "SELECT SUM(ss_ext_sales_price) FROM store_sales")
    assert any(row[0] is None for row in got.rows)
    assert sum(row[1] for row in got.rows) == grand_total


def test_no_dimensions_gives_one_global_row(engine, con):
    got = engine.query(QueryRequest(metrics=["total_sales", "total_profit"]))
    assert got.rows == oracle(con, "SELECT SUM(ss_ext_sales_price), SUM(ss_net_profit) FROM store_sales")


def test_overcount_warning_reaches_the_result(engine):
    got = engine.query(QueryRequest(metrics=["store_productivity"], dimensions=["store.s_state"]))
    assert got.warnings and "store_productivity" in got.warnings[0]


def test_to_dicts(engine):
    rows = engine.query(QueryRequest(metrics=["total_sales"], dimensions=["date_dim.d_year"])).to_dicts()
    assert set(rows[0]) == {"d_year", "total_sales"} and isinstance(rows[0]["total_sales"], Decimal)


def test_duckdb_errors_become_query_errors(engine):
    # no GROUP BY dimension for a window metric that needs one
    with pytest.raises(QueryError) as exc:
        engine.query(QueryRequest(metrics=["cumulative_sales"]))
    assert "DuckDB rejected" in str(exc.value)


def test_check_sources_reports_missing_tables(model):
    empty = Engine(model, duckdb.connect(), rebind={"tpcds.public": "main"})
    problems = empty.check_sources()
    assert len(problems) == 5 and "store_sales" in problems[0]


def test_check_sources_passes_on_real_tables(engine):
    assert engine.check_sources() == []


def test_filter_values_are_data_not_sql(engine):
    got = engine.query(
        QueryRequest(metrics=["total_sales"], filters=["store.s_state = 'CA'' OR 1=1 --'"])
    )
    assert got.rows == [(None,)]  # matches nothing; the quote did not break out of the literal


def test_synthetic_data_is_deterministic(con):
    assert oracle(con, "SELECT count(*), sum(ss_quantity) FROM store_sales") == [(6000, 33000)]
    # the generator keeps (item, ticket) unique, as in real TPC-DS
    assert oracle(con, "SELECT count(*) FROM (SELECT DISTINCT ss_item_sk, ss_ticket_number FROM store_sales)") == [(6000,)]
