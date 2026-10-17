"""One-time backfill: 20 years of OHLCV + NAVs.

Trigger manually from the Airflow UI. Stocks are loaded in chunks so a yfinance
hiccup on one chunk doesn't blow up the whole run; the loader's DELETE-INSERT
upsert makes retries idempotent.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _lib import triaged

DEFAULT_ARGS = {
    "owner": "data-eng",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

CHUNK_SIZE = 25  # tickers per yfinance request

# Hand-picked 30 schemes — Regular-Growth plans across category + AMC for
# diversity, biased toward long NAV history (most launched pre-2010, several
# from the 90s). Direct plans only began in 2013 so cap history at ~13 yrs;
# Regular plans give us closer to the 20-year backfill horizon.
CURATED_SCHEME_CODES = [
    # Large cap (6)
    100471,  # Franklin India Large Cap (erstwhile Bluechip)
    102000,  # HDFC Large Cap Fund (erstwhile Top 100)
    103504,  # SBI Large Cap Fund (erstwhile Magnum Equity)
    106235,  # Nippon India Large Cap Fund
    107578,  # Mirae Asset Large Cap Fund
    108466,  # ICICI Prudential Large Cap (erstwhile Bluechip)
    # Flexi / multi cap (5)
    100669,  # UTI Flexi Cap Fund
    101762,  # HDFC Flexi Cap (erstwhile Equity)
    103215,  # SBI Flexicap Fund
    109830,  # quant Flexi Cap Fund
    122640,  # Parag Parikh Flexi Cap Fund
    # Mid cap (4)
    100377,  # Nippon India Growth Mid Cap Fund
    102941,  # SBI Midcap Fund
    104481,  # DSP Midcap Fund
    105758,  # HDFC Mid Cap Fund
    # Small cap (3)
    100177,  # quant Small Cap Fund
    113177,  # Nippon India Small Cap Fund
    125494,  # SBI Small Cap Fund
    # ELSS / tax saver (4)
    100175,  # quant ELSS Tax Saver Fund
    101979,  # HDFC ELSS Tax Saver
    104331,  # Aditya Birla Sun Life Tax Plan
    104772,  # DSP ELSS Tax Saver Fund
    # Hybrid / balanced (4)
    100119,  # HDFC Balanced Advantage Fund
    100356,  # ICICI Prudential Equity & Debt Fund
    102885,  # SBI Equity Hybrid Fund
    103155,  # Aditya Birla Sun Life Equity Hybrid '95 Fund
    # Index (3)
    100822,  # UTI Nifty 50 Index Fund
    102272,  # SBI Nifty Index Fund
    113269,  # Nippon India Index Fund - BSE Sensex
    # Value / contra (1)
    102594,  # ICICI Prudential Value Fund (erstwhile Value Discovery)
]


@dag(
    dag_id="history_backfill",
    description="20-year backfill of stocks + mutual fund NAVs (manual trigger)",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["markets", "backfill", "manual"],
)
def history_backfill_dag():

    @task
    @triaged(downstream=['backfill_stocks', 'backfill_navs', 'daily_prices'])
    def refresh_universe() -> dict:
        import polars as pl

        from markets_pipeline.config import CONFIG
        from markets_pipeline.extractors import universe

        from _lib import open_loader

        tickers = universe.get_stock_universe(CONFIG.stock_universe)
        master = universe.fetch_mf_scheme_master()
        stock_universe_df = pl.DataFrame(
            {"ticker": tickers, "universe": [CONFIG.stock_universe] * len(tickers)}
        )

        with open_loader() as (_, loader):
            su = loader.load("stock_universe", stock_universe_df, ["ticker"])
            mm = loader.load("mf_scheme_master", master, ["scheme_code"])

        return {"stocks": su.rows_loaded, "mf_master": mm.rows_loaded}

    @task
    @triaged(downstream=['feature_build', 'stock_features', 'stock_recommendations', 'educational Streamlit dashboard (not financial advice)'])
    def backfill_stocks() -> dict:
        from datetime import date, timedelta as td

        from markets_pipeline.config import CONFIG
        from markets_pipeline.extractors import stocks, universe

        from _lib import open_loader

        end = date.today()
        start = end - td(days=365 * CONFIG.backfill_years)
        tickers = universe.get_stock_universe(CONFIG.stock_universe)

        total_loaded = 0
        with open_loader() as (_, loader):
            for i in range(0, len(tickers), CHUNK_SIZE):
                chunk = tickers[i : i + CHUNK_SIZE]
                df = stocks.fetch_prices(chunk, start=start, end=end)
                result = loader.load("stock_prices", df, ["ticker", "date"])
                total_loaded += result.rows_loaded

        return {
            "tickers": len(tickers),
            "loaded": total_loaded,
            "years": CONFIG.backfill_years,
        }

    @task
    @triaged(downstream=['feature_build', 'mf_features', 'mf_recommendations', 'educational Streamlit dashboard (not financial advice)'])
    def backfill_navs() -> dict:
        from datetime import date, timedelta as td

        from markets_pipeline.config import CONFIG
        from markets_pipeline.extractors import mutual_funds

        from _lib import open_loader

        end = date.today()
        start = end - td(days=365 * CONFIG.backfill_years)

        df = mutual_funds.fetch_navs(CURATED_SCHEME_CODES, since=start)

        with open_loader() as (_, loader):
            result = loader.load("mf_navs", df, ["scheme_code", "date"])

        return {"schemes": len(CURATED_SCHEME_CODES), "loaded": result.rows_loaded}

    # DuckDB allows only one writer process. Chain tasks sequentially.
    refresh_universe() >> backfill_stocks() >> backfill_navs()


history_backfill_dag()
