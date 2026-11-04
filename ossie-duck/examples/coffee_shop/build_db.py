"""Build coffee_shop.duckdb from the two CSV files next to this script.

    python examples/coffee_shop/build_db.py [output.duckdb]

The database is generated on demand and is not committed to git.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent


def build(db_path: str | Path | None = None) -> Path:
    db_path = Path(db_path) if db_path else HERE / "coffee_shop.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for table, columns in {
            "customers": "CAST(customer_id AS INTEGER) AS customer_id, name, country",
            "orders": (
                "CAST(order_id AS INTEGER) AS order_id, CAST(customer_id AS INTEGER) AS customer_id, product, "
                "CAST(quantity AS INTEGER) AS quantity, CAST(unit_price AS DECIMAL(8, 2)) AS unit_price, "
                "CAST(order_date AS DATE) AS order_date"
            ),
        }.items():
            csv = (HERE / f"{table}.csv").as_posix().replace("'", "''")
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT {columns} FROM read_csv('{csv}', header = true)")
    finally:
        con.close()
    return db_path


if __name__ == "__main__":
    path = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"built {path}")
