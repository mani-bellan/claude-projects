"""Airflow DAG: extract -> sense -> transform -> quality gate -> load -> archive.

Schedule: daily. Each run pulls the logical date's weather, lands a raw JSON
file, waits for it, cleans it to Parquet, checks quality, and upserts into
DuckDB. The DuckDB load is idempotent (delete+insert by run_date), so backfills
and re-runs are safe.

Place (or symlink) this file into your AIRFLOW_HOME/dags/ folder. The pipeline
modules live in this repo, so set PIPELINE_HOME below or via env var.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.sensors.filesystem import FileSensor

# Resolve the repo root so we can import the extractor + ETL modules. Override
# with PIPELINE_HOME if the DAG is symlinked from elsewhere.
PIPELINE_HOME = Path(os.environ.get("PIPELINE_HOME", Path(__file__).resolve().parents[1]))
if str(PIPELINE_HOME) not in sys.path:
    sys.path.insert(0, str(PIPELINE_HOME))

SOURCE_DIR = PIPELINE_HOME / "data" / "source"

default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="weather_india_pipeline",
    description="Pull Indian city weather from Open-Meteo into DuckDB",
    schedule="@daily",
    start_date=datetime(2026, 6, 1),
    catchup=False,
    default_args=default_args,
    tags=["weather", "india", "duckdb", "open-meteo"],
)
def weather_india_pipeline():

    @task
    def extract(ds: str | None = None) -> str:
        """Pull all cities for the logical date into data/source/."""
        from datetime import date
        from extract.extract_weather import fetch_weather, write_landing_file

        run_date = date.fromisoformat(ds) if ds else date.today()
        data = fetch_weather(run_date)
        out_path = write_landing_file(data, run_date)
        return str(out_path)

    # Wait for the landing file. reschedule mode frees the worker slot between
    # pokes instead of holding it.
    wait_for_file = FileSensor(
        task_id="wait_for_landing_file",
        filepath="{{ ti.xcom_pull(task_ids='extract') }}",
        fs_conn_id="fs_default",
        poke_interval=15,
        timeout=300,
        mode="reschedule",
    )

    @task
    def transform(source_file: str) -> str:
        from dags.weather_etl import transform as _transform
        return _transform(source_file)

    @task
    def quality_gate(staging_file: str) -> str:
        from dags.weather_etl import quality_check
        quality_check(staging_file)
        return staging_file

    @task
    def load(staging_file: str) -> int:
        from dags.weather_etl import load as _load
        return _load(staging_file)

    @task
    def archive(source_file: str, _load_done: int) -> str:
        # _load_done is an unused dependency arg: forces archive to run only
        # after a successful load.
        from dags.weather_etl import archive as _archive
        return _archive(source_file)

    source_path = extract()
    source_path >> wait_for_file

    staging_path = transform(source_path)
    checked = quality_gate(staging_path)
    loaded = load(checked)
    archive(source_path, loaded)


weather_india_pipeline()
