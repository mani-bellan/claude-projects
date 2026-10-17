"""Daily: pull yesterday's OHLCV for the configured universe."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _lib import triaged

DEFAULT_ARGS = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="daily_prices",
    description="Yesterday's OHLCV for the stock universe",
    schedule="30 12 * * 1-5",          # Mon–Fri 12:30 UTC = 6:00 PM IST after close
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["markets", "stocks", "daily"],
)
def daily_prices_dag():

    @task
    @triaged(downstream=['feature_build', 'stock_features', 'stock_recommendations', 'educational Streamlit dashboard (not financial advice): Recommendations, Stock Explorer, Portfolio Simulator pages'])
    def fetch_and_load(data_interval_end=None) -> dict:
        from datetime import date, timedelta as td

        from markets_pipeline.config import CONFIG
        from markets_pipeline.extractors import stocks, universe

        from _lib import open_loader

        run_date = (data_interval_end.date() if data_interval_end else date.today())
        target = run_date - td(days=1)

        tickers = universe.get_stock_universe(CONFIG.stock_universe)
        df = stocks.fetch_prices(tickers, start=target, end=target)

        with open_loader() as (_, loader):
            result = loader.load("stock_prices", df, ["ticker", "date"])

        return {
            "target_date": str(target),
            "tickers": len(tickers),
            "loaded": result.rows_loaded,
            "rejected": result.rows_rejected,
        }

    fetch_and_load()


daily_prices_dag()
