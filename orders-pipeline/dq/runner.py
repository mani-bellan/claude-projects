"""Data quality rule engine.

Row rules evaluate a normalized (canonical, typed) record and return failed
rule names; silver quarantines any row with failures. Batch rules run SQL
against the warehouse after promotion and alert without quarantining.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import yaml

DEFAULT_RULES_PATH = Path(__file__).parent / "rules.yaml"


class RuleSet:
    def __init__(self, spec: dict):
        self.row_rules = spec.get("row_rules", [])
        self.batch_rules = spec.get("batch_rules", [])
        self._severity = {r["name"]: r.get("severity", "warning")
                          for r in self.row_rules + self.batch_rules}

    @classmethod
    def load(cls, path: str | Path = DEFAULT_RULES_PATH) -> "RuleSet":
        return cls(yaml.safe_load(Path(path).read_text()))

    def severity_of(self, name: str) -> str:
        # uncastable_* pseudo-rules come from cast failures, always critical
        return self._severity.get(name, "critical")

    # ---- row rules ----

    def evaluate_row(self, record: dict, now: datetime | None = None) -> list[str]:
        now = now or datetime.now(timezone.utc)
        failed = []
        for rule in self.row_rules:
            if not _CHECKS[rule["check"]](record, rule, now):
                failed.append(rule["name"])
        return failed

    # ---- batch rules ----

    def evaluate_batch(self, con: duckdb.DuckDBPyConnection, batch_id: str,
                       now: datetime | None = None) -> list[dict]:
        """Run batch rules, persist to meta.dq_results, return the results."""
        now = now or datetime.now(timezone.utc)
        results = []
        for rule in self.batch_rules:
            passed, detail, failed_n, total_n = _BATCH_CHECKS[rule["type"]](
                con, batch_id, rule, now)
            results.append({"rule_name": rule["name"], "passed": passed,
                            "severity": rule.get("severity", "warning"),
                            "detail": detail})
            con.execute(
                "INSERT INTO meta.dq_results VALUES (?, 'batch', ?, ?, ?, ?, ?, ?, ?)",
                [batch_id, rule["name"], rule.get("severity", "warning"),
                 passed, failed_n, total_n, detail, now])
        return results


# ---- row check implementations: (record, rule, now) -> passed ----

def _check_not_null(rec, rule, now):
    return rec.get(rule["column"]) is not None


def _check_in_set(rec, rule, now):
    v = rec.get(rule["column"])
    if v is None:
        return bool(rule.get("allow_null"))
    return v in rule["values"]


def _check_range(rec, rule, now):
    v = rec.get(rule["column"])
    if v is None:
        return bool(rule.get("allow_null"))
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    return rule["min"] <= v <= rule["max"]


def _check_ts_not_future(rec, rule, now):
    v = rec.get(rule["column"])
    if v is None:
        return True  # nullness is order_ts_not_null's job
    return v <= now + timedelta(minutes=rule.get("tolerance_minutes", 0))


def _check_ts_not_older_days(rec, rule, now):
    v = rec.get(rule["column"])
    if v is None:
        return True
    return v >= now - timedelta(days=rule["days"])


def _check_negative_only_for_status(rec, rule, now):
    v = rec.get(rule["column"])
    if v is None or v >= 0:
        return True
    return rec.get(rule["status_column"]) == rule["allowed_status"]


def _check_items_nonempty_unless_status(rec, rule, now):
    if rec.get("status") in rule.get("exempt_statuses", []):
        return True
    items = rec.get(rule["column"])
    return isinstance(items, list) and len(items) > 0


_CHECKS = {
    "not_null": _check_not_null,
    "in_set": _check_in_set,
    "range": _check_range,
    "ts_not_future": _check_ts_not_future,
    "ts_not_older_days": _check_ts_not_older_days,
    "negative_only_for_status": _check_negative_only_for_status,
    "items_nonempty_unless_status": _check_items_nonempty_unless_status,
}


# ---- batch check implementations: -> (passed, detail, failed_n, total_n) ----

def _batch_volume_band(con, batch_id, rule, now):
    current = con.execute(
        "SELECT row_count FROM meta.processed_batches WHERE batch_id = ?",
        [batch_id]).fetchone()
    if current is None:
        return True, "batch not found (skipped)", 0, 0
    current_n = current[0]
    history = con.execute("""
        SELECT row_count FROM meta.processed_batches
        WHERE batch_id != ? AND status IN ('loaded', 'promoted')
        ORDER BY processed_at DESC LIMIT ?
    """, [batch_id, rule["lookback_batches"]]).fetchall()
    if len(history) < rule.get("min_history", 3):
        return True, f"insufficient history ({len(history)} batches)", 0, current_n
    avg = sum(h[0] for h in history) / len(history)
    factor = rule["band_factor"]
    lo, hi = avg / factor, avg * factor
    passed = lo <= current_n <= hi
    return passed, f"rows={current_n} band=[{lo:.0f},{hi:.0f}] avg={avg:.0f}", \
        0 if passed else current_n, current_n


def _batch_freshness(con, batch_id, rule, now):
    newest = con.execute("""
        SELECT MAX(order_ts) FROM silver.orders_events WHERE batch_id = ?
    """, [batch_id]).fetchone()[0]
    if newest is None:
        return True, "no promoted rows (skipped)", 0, 0
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    lag = (now - newest).total_seconds() / 60
    passed = lag <= rule["max_lag_minutes"]
    return passed, f"lag_minutes={lag:.1f}", 0 if passed else 1, 1


_BATCH_CHECKS = {
    "volume_band": _batch_volume_band,
    "freshness": _batch_freshness,
}
