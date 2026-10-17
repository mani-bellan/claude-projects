"""Daily: pull mutual fund NAVs for the curated SIP universe.

Phase 4 expands the curated list. Until then, use the smoke set so the daily
DAG stays cheap and predictable.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from _lib import triaged

DEFAULT_ARGS = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

CURATED_SCHEME_CODES = [
    120503,  # Parag Parikh Flexi Cap (Direct, Growth)
    119598,  # UTI Nifty 50 Index (Direct, Growth)
    118989,  # HDFC Index Fund - Sensex (Direct, Growth)
    122639,  # Mirae Asset Large Cap (Direct, Growth)
    120716,  # Axis Long Term Equity ELSS (Direct, Growth)
]


@dag(
    dag_id="daily_navs",
    description="Yesterday's NAVs for the curated mutual fund universe",
    schedule="0 14 * * *",             # 14:00 UTC = 7:30 PM IST (AMFI publishes ~7 PM)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["markets", "mutual-funds", "daily"],
)
def daily_navs_dag():

    @task
    @triaged(downstream=['feature_build', 'mf_features', 'mf_recommendations', 'educational Streamlit dashboard (not financial advice): SIP Recommender, Portfolio Simulator pages'])
    def fetch_and_load(data_interval_end=None) -> dict:
        from datetime import date, timedelta as td

        from markets_pipeline.extractors import mutual_funds

        from _lib import open_loader

        run_date = (data_interval_end.date() if data_interval_end else date.today())
        target = run_date - td(days=1)

        df = mutual_funds.fetch_navs(CURATED_SCHEME_CODES, since=target)

        with open_loader() as (_, loader):
            result = loader.load("mf_navs", df, ["scheme_code", "date"])

        return {
            "target_date": str(target),
            "schemes": len(CURATED_SCHEME_CODES),
            "loaded": result.rows_loaded,
            "rejected": result.rows_rejected,
        }

    fetch_and_load()


daily_navs_dag()
