"""Sample data for the bundled TPC-DS example model.

``load_synthetic_tpcds`` builds small deterministic tables with exactly the
columns the example model uses, so everything works offline. Values are generated
with plain arithmetic (no hashing or randomness), so they are identical on every
DuckDB version.

``load_tpcds_extension`` loads real TPC-DS data through DuckDB's ``tpcds``
extension; that needs network access the first time to install the extension.
"""

from __future__ import annotations

import duckdb

N_DATES, N_ITEMS, N_STORES, N_CUSTOMERS, N_SALES = 730, 40, 6, 200, 6000


def load_synthetic_tpcds(con: duckdb.DuckDBPyConnection, schema: str = "main") -> None:
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    s = f'"{schema}"'

    con.execute(f"""
        CREATE OR REPLACE TABLE {s}.date_dim AS
        SELECT d_date_sk, d_date,
               year(d_date) AS d_year,
               month(d_date) AS d_moy,
               CAST(year(d_date) AS VARCHAR) || 'Q' || CAST(quarter(d_date) AS VARCHAR) AS d_quarter_name
        FROM (
            SELECT i + 1 AS d_date_sk, DATE '2023-01-01' + CAST(i AS INTEGER) AS d_date
            FROM range({N_DATES}) t(i)
        )""")

    con.execute(f"""
        CREATE OR REPLACE TABLE {s}.item AS
        SELECT i + 1 AS i_item_sk,
               'ITEM' || lpad(CAST(i + 1 AS VARCHAR), 6, '0') AS i_item_id,
               'Item description ' || CAST(i + 1 AS VARCHAR) AS i_item_desc,
               'Brand#' || CAST(i % 8 + 1 AS VARCHAR) AS i_brand,
               (['Books', 'Electronics', 'Home', 'Music', 'Shoes'])[i % 5 + 1] AS i_category,
               CAST(5.99 + (i * 37) % 95 AS DECIMAL(7, 2)) AS i_current_price
        FROM range({N_ITEMS}) t(i)""")

    con.execute(f"""
        CREATE OR REPLACE TABLE {s}.store AS
        SELECT i + 1 AS s_store_sk,
               'STORE' || lpad(CAST(i + 1 AS VARCHAR), 4, '0') AS s_store_id,
               'Store ' || CAST(i + 1 AS VARCHAR) AS s_store_name,
               (['Oakland', 'Albany', 'Austin', 'Seattle', 'Chicago', 'Miami'])[i % 6 + 1] AS s_city,
               (['CA', 'NY', 'TX', 'WA', 'IL', 'FL'])[i % 6 + 1] AS s_state,
               40 + (i * 13) % 50 AS s_number_employees
        FROM range({N_STORES}) t(i)""")

    con.execute(f"""
        CREATE OR REPLACE TABLE {s}.customer AS
        SELECT i + 1 AS c_customer_sk,
               'CUST' || lpad(CAST(i + 1 AS VARCHAR), 8, '0') AS c_customer_id,
               (['Ava', 'Ben', 'Chen', 'Dia', 'Eli', 'Fay', 'Gus', 'Hana'])[i % 8 + 1] AS c_first_name,
               (['Patel', 'Silva', 'Kim', 'Okafor', 'Rossi', 'Nguyen', 'Haas'])[i % 7 + 1] AS c_last_name,
               'customer' || CAST(i + 1 AS VARCHAR) || '@example.com' AS c_email_address
        FROM range({N_CUSTOMERS}) t(i)""")

    # Ticket groups of 3 lines. Consecutive items differ by 31 or 32 (mod 40), so
    # (item, ticket) stays unique; the `i // k` terms decorrelate stores and items.
    con.execute(f"""
        CREATE OR REPLACE TABLE {s}.store_sales AS
        SELECT ss_sold_date_sk, ss_item_sk, ss_ticket_number, ss_customer_sk, ss_store_sk,
               ss_quantity, ss_sales_price,
               CAST(ss_quantity * ss_sales_price AS DECIMAL(12, 2)) AS ss_ext_sales_price,
               CAST(ss_quantity * ss_sales_price * ((i * 11) % 40 - 8) / 100.0 AS DECIMAL(12, 2)) AS ss_net_profit
        FROM (
            SELECT i,
                   1 + (i * 7919) % {N_DATES} AS ss_sold_date_sk,
                   1 + (i * 31 + i // 11) % {N_ITEMS} AS ss_item_sk,
                   i // 3 + 1 AS ss_ticket_number,
                   1 + (i * 17 + i // 13) % {N_CUSTOMERS} AS ss_customer_sk,
                   1 + (i * 5 + i // 7) % {N_STORES} AS ss_store_sk,
                   1 + (i * 3) % 10 AS ss_quantity,
                   CAST(5 + ((i * 13) % 9500) / 100.0 AS DECIMAL(7, 2)) AS ss_sales_price
            FROM range({N_SALES}) t(i)
        )""")


def load_tpcds_extension(con: duckdb.DuckDBPyConnection, scale: float = 0.01) -> None:
    """Generate real TPC-DS tables into ``main`` using DuckDB's tpcds extension."""
    con.execute("INSTALL tpcds")
    con.execute("LOAD tpcds")
    con.execute(f"CALL dsdgen(sf = {float(scale)})")
