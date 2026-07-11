"""Daily: rebuild features + recommendations from the latest prices/NAVs.

Scheduled to fire after both daily_prices and daily_navs land. Cheap enough
that we always rebuild the whole feature/recommendation tables instead of
trying to incrementalize.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

DEFAULT_ARGS = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="feature_build",
    description="Compute features + long-term recommendations",
    schedule="0 16 * * *",            # 16:00 UTC = 21:30 IST, after daily_navs
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["markets", "features", "daily"],
)
def feature_build_dag():

    @task
    def build() -> dict:
        from markets_pipeline.transformers import _pipeline

        return _pipeline.build_all()

    build()


feature_build_dag()
