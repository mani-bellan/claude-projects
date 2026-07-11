"""Medallion pipeline DAG: sense -> ingest -> promote -> gold -> metrics.

All logic lives in pipeline/; tasks here only wire XCom between the
entry points in pipeline/run.py. Only ever reads the landing zone — never
assumes the simulator DAG exists.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.exceptions import AirflowSkipException

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _run():
    from pipeline.run import Paths
    return Paths()


@dag(
    dag_id="orders_medallion",
    schedule="*/15 * * * *",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,  # serialized runs: no landing-zone or dedup races
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["orders", "medallion"],
)
def orders_medallion():
    @task
    def sense_landing_zone() -> list[str]:
        from pipeline.run import sense
        waiting = sense(_run())
        if not waiting:
            raise AirflowSkipException("no new files in landing zone")
        return waiting

    @task
    def load_bronze(waiting: list[str]) -> list[str]:
        from pipeline.run import ingest
        results = ingest(_run())
        errors = [r for r in results if r.get("error")]
        for e in errors:
            print(f"batch {e['batch_id']} failed ingestion: {e['error']}")
        for r in results:
            if r.get("drift") and r["drift"]["classification"] not in ("baseline",):
                print(f"schema drift in {r['batch_id']}: {r['drift']}")
        return [r["batch_id"] for r in results if not r.get("skipped") and not r.get("error")]

    @task
    def promote_silver(batch_ids: list[str]) -> dict:
        from pipeline.run import promote
        results = promote(_run(), batch_ids)
        halted = [r["batch_id"] for r in results if r["halted"]]
        return {"batch_ids": [r["batch_id"] for r in results], "halted": halted}

    @task
    def build_gold(promoted: dict) -> dict:
        from pipeline.run import build_gold as build
        return build(_run())

    @task
    def publish_metrics(promoted: dict) -> None:
        from pipeline.run import publish_metrics as publish
        breaches = publish(_run(), promoted["batch_ids"])
        for b in breaches:
            print(f"DQ ALERT [{b['severity']}] {b['rule_name']} "
                  f"batch={b['batch_id']}: {b['detail']}")
        # hook alerting here: Slack/email callback on breaches
        if promoted["halted"]:
            # fail last so gold still built for healthy batches this run
            raise RuntimeError(
                f"systemic DQ failure, batches halted: {promoted['halted']}")

    waiting = sense_landing_zone()
    loaded = load_bronze(waiting)
    promoted = promote_silver(loaded)
    build_gold(promoted) >> publish_metrics(promoted)


orders_medallion()
