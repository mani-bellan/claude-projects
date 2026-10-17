"""Weekly: refresh the stock universe + AMFI scheme master.

Stock universe is stored as a single-column table so other DAGs can join on it.
Mutual fund master enables category/AUM filters when the recommendation engine
expands beyond the smoke universe.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _lib import triaged

DEFAULT_ARGS = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="universe_refresh",
    description="Refresh Nifty 500 stock list + AMFI mutual fund master",
    schedule="0 18 * * SUN",          # Sunday 18:00 UTC = Mon 23:30 IST
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["markets", "universe"],
)
def universe_refresh_dag():

    @task
    @triaged(downstream=['daily_prices', 'stock_universe'])
    def refresh_stocks() -> int:
        import polars as pl

        from markets_pipeline.config import CONFIG
        from markets_pipeline.extractors import universe

        from _lib import open_loader

        tickers = universe.get_stock_universe(CONFIG.stock_universe)
        df = pl.DataFrame({"ticker": tickers, "universe": [CONFIG.stock_universe] * len(tickers)})
        with open_loader() as (_, loader):
            result = loader.load("stock_universe", df, ["ticker"])
        return result.rows_loaded

    @task
    @triaged(downstream=['mf_scheme_master'])
    def refresh_mfs() -> int:
        from markets_pipeline.extractors import universe

        from _lib import open_loader

        df = universe.fetch_mf_scheme_master()
        with open_loader() as (_, loader):
            result = loader.load("mf_scheme_master", df, ["scheme_code"])
        return result.rows_loaded

    refresh_stocks() >> refresh_mfs()


universe_refresh_dag()
