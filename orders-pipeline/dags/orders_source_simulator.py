"""Source-system simulator DAG.

Deliberately independent of the pipeline DAG: shares nothing but the landing
zone directory. Pause this DAG to test the pipeline's no-new-files skip path,
or swap it for cron / a real upstream without touching pipeline code.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task

PROJECT_ROOT = Path(__file__).parent.parent


@dag(
    dag_id="orders_source_simulator",
    schedule="*/15 * * * *",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["orders", "source"],
)
def orders_source_simulator():
    @task
    def generate_batch() -> dict:
        sys.path.insert(0, str(PROJECT_ROOT))
        from generator.generate import generate_batch as gen
        return gen(
            landing_dir=PROJECT_ROOT / "warehouse" / "landing" / "incoming",
            state_path=PROJECT_ROOT / "warehouse" / "generator_state.json",
        )

    generate_batch()


orders_source_simulator()
