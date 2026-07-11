"""Task-level entry points. DAGs are thin wrappers around these functions,
so the whole pipeline is runnable and testable without Airflow.
"""

from __future__ import annotations

import json
from pathlib import Path

from dq.runner import RuleSet
from pipeline import bronze, gold, silver, warehouse
from pipeline.landing import discover_batches
from pipeline.schema_registry import register_batch_schema

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = PROJECT_ROOT / "warehouse" / "orders.duckdb"
DEFAULT_LANDING = PROJECT_ROOT / "warehouse" / "landing"


class Paths:
    def __init__(self, db_path=DEFAULT_DB, landing_root=DEFAULT_LANDING):
        self.db_path = Path(db_path)
        landing_root = Path(landing_root)
        self.incoming = landing_root / "incoming"
        self.processed = landing_root / "processed"
        self.failed = landing_root / "failed"


def sense(paths: Paths) -> list[str]:
    """Return batch_ids waiting in the landing zone (for short-circuit)."""
    return [b.batch_id for b in discover_batches(paths.incoming)]


def ingest(paths: Paths) -> list[dict]:
    """Register schemas + load all waiting batches into bronze."""
    con = warehouse.connect(paths.db_path)
    try:
        batches = discover_batches(paths.incoming)
        results = []
        for batch in batches:
            drift = None
            try:
                from pipeline.landing import read_and_verify
                records = read_and_verify(batch)
                report = register_batch_schema(con, batch.batch_id, records)
                drift = {"classification": report.classification, "is_new": report.is_new,
                         "added": report.added, "removed": report.removed,
                         "type_changed": report.type_changed}
            except Exception:
                pass  # unreadable file: bronze load below records the failure
            result = bronze.ingest_incoming(con, [batch], paths.processed, paths.failed)[0]
            result["drift"] = drift
            results.append(result)
        return results
    finally:
        con.close()


def promote(paths: Paths, batch_ids: list[str] | None = None,
            rules_path=None) -> list[dict]:
    """Promote loaded batches to silver. Defaults to all in 'loaded' state."""
    con = warehouse.connect(paths.db_path)
    try:
        ruleset = RuleSet.load(rules_path) if rules_path else RuleSet.load()
        if batch_ids is None:
            batch_ids = [b for (b,) in con.execute(
                "SELECT batch_id FROM meta.processed_batches WHERE status = 'loaded' "
                "ORDER BY processed_at").fetchall()]
        return [silver.promote_batch(con, b, ruleset) for b in batch_ids]
    finally:
        con.close()


def build_gold(paths: Paths) -> dict[str, int]:
    con = warehouse.connect(paths.db_path)
    try:
        return gold.build_all(con)
    finally:
        con.close()


def publish_metrics(paths: Paths, batch_ids: list[str], rules_path=None) -> list[dict]:
    """Run batch-level DQ rules; returns breaches for the DAG to alert on."""
    con = warehouse.connect(paths.db_path)
    try:
        ruleset = RuleSet.load(rules_path) if rules_path else RuleSet.load()
        breaches = []
        for batch_id in batch_ids:
            for result in ruleset.evaluate_batch(con, batch_id):
                if not result["passed"]:
                    breaches.append({"batch_id": batch_id, **result})
        return breaches
    finally:
        con.close()


def run_once(paths: Paths | None = None, rules_path=None) -> dict:
    """Full pipeline pass — what one DAG run does. Used by tests and CLI."""
    paths = paths or Paths()
    waiting = sense(paths)
    if not waiting:
        return {"skipped": True, "reason": "no new files"}
    ingest_results = ingest(paths)
    loaded = [r["batch_id"] for r in ingest_results if not r.get("skipped") and not r.get("error")]
    promote_results = promote(paths, loaded, rules_path=rules_path)
    gold_counts = build_gold(paths)
    breaches = publish_metrics(paths, loaded, rules_path=rules_path)
    return {"skipped": False, "ingested": ingest_results, "promoted": promote_results,
            "gold": gold_counts, "dq_breaches": breaches}


if __name__ == "__main__":
    print(json.dumps(run_once(), indent=2, default=str))
