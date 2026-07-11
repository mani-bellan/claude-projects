"""Manual replay DAG.

Trigger with config {"batch_id": "<id>"} to re-promote a batch through the
same silver/gold code — e.g. after registering a column alias for a rename,
or fixing a rule. Promotion is idempotent (delete-then-insert by batch_id),
so replays converge instead of double counting.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task

PROJECT_ROOT = Path(__file__).parent.parent


@dag(
    dag_id="orders_reprocess",
    schedule=None,  # manual trigger only
    start_date=datetime(2026, 7, 1),
    catchup=False,
    params={"batch_id": ""},
    tags=["orders", "ops"],
)
def orders_reprocess():
    @task
    def replay(**context) -> dict:
        sys.path.insert(0, str(PROJECT_ROOT))
        from pipeline.run import Paths, build_gold, promote

        batch_id = context["params"]["batch_id"]
        if not batch_id:
            raise ValueError("trigger with config {'batch_id': '<id>'}")
        paths = Paths()
        result = promote(paths, [batch_id])[0]
        build_gold(paths)
        return result

    replay()


orders_reprocess()
