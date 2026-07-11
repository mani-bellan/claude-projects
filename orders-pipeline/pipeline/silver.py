"""Silver layer: parse, alias, safe-cast, dedup, DQ gate, quarantine, upsert.

Promotion is quarantine-and-continue: bad rows are set aside individually,
but a batch whose failure rate exceeds QUARANTINE_HALT_THRESHOLD is treated
as systemically broken and promotes nothing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import duckdb

from pipeline.schema_registry import CANONICAL_COLUMNS, apply_aliases, load_aliases

QUARANTINE_HALT_THRESHOLD = 0.20

_AMOUNT_RE = re.compile(r"^-?[\d,]+(\.\d+)?$")
_DDMMYYYY_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})$")


class CastError(Exception):
    def __init__(self, column: str, value):
        self.column = column
        super().__init__(f"uncastable_{column}: {value!r}")


def cast_amount(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise CastError("total_amount", value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().lstrip("₹$€£").replace(",", "")
        if _AMOUNT_RE.match(cleaned):
            return float(cleaned)
    raise CastError("total_amount", value)


def cast_timestamp(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            ts = datetime.fromisoformat(value)
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        m = _DDMMYYYY_RE.match(value.strip())
        if m:
            dd, mm, yyyy, hh, mi = m.groups()
            try:
                return datetime(int(yyyy), int(mm), int(dd), int(hh), int(mi),
                                tzinfo=timezone.utc)
            except ValueError as e:
                raise CastError("order_ts", value) from e
    raise CastError("order_ts", value)


def normalize(record: dict, aliases: dict[str, str]) -> dict:
    """Alias + cast one raw record to canonical shape; extras carry the rest."""
    rec = apply_aliases(record, aliases)
    out = {
        "order_id": rec.get("order_id"),
        "customer_id": rec.get("customer_id"),
        "customer_name": rec.get("customer_name"),
        "order_ts": cast_timestamp(rec.get("order_ts")),
        "status": rec.get("status"),
        "currency": rec.get("currency"),
        "total_amount": cast_amount(rec.get("total_amount")),
        "items": rec.get("items"),
    }
    extras = {k: v for k, v in rec.items() if k not in CANONICAL_COLUMNS}
    out["extras"] = extras or None
    return out


def promote_batch(con: duckdb.DuckDBPyConnection, batch_id: str, ruleset) -> dict:
    """Promote one bronze batch to silver. Idempotent by batch_id.

    Returns {batch_id, promoted, quarantined, deduped, halted}.
    """
    rows = con.execute(
        "SELECT record_hash, raw FROM bronze.orders_raw WHERE batch_id = ?",
        [batch_id]).fetchall()
    aliases = load_aliases(con)
    now = datetime.now(timezone.utc)

    good: list[tuple[str, dict]] = []
    quarantined: list[tuple[str, list[str], str]] = []
    rule_failures: dict[str, int] = {}
    seen_hashes: set[str] = set()
    deduped = 0

    for r_hash, raw in rows:
        if r_hash in seen_hashes:
            deduped += 1
            continue
        seen_hashes.add(r_hash)
        record = json.loads(raw)
        try:
            normalized = normalize(record, aliases)
        except CastError as e:
            rule_failures[f"uncastable_{e.column}"] = rule_failures.get(f"uncastable_{e.column}", 0) + 1
            quarantined.append((r_hash, [f"uncastable_{e.column}"], raw))
            continue
        failed = ruleset.evaluate_row(normalized)
        if failed:
            for name in failed:
                rule_failures[name] = rule_failures.get(name, 0) + 1
            quarantined.append((r_hash, failed, raw))
        else:
            good.append((r_hash, normalized))

    total = len(good) + len(quarantined)
    fail_rate = (len(quarantined) / total) if total else 0.0
    halted = total > 0 and fail_rate > QUARANTINE_HALT_THRESHOLD

    con.execute("BEGIN")
    try:
        # Idempotent replay: clear anything this batch wrote before.
        con.execute("DELETE FROM silver.orders_events WHERE batch_id = ?", [batch_id])
        con.execute("DELETE FROM silver.quarantine WHERE batch_id = ?", [batch_id])

        for r_hash, failed, raw in quarantined:
            con.execute("INSERT INTO silver.quarantine VALUES (?, ?, ?, ?, ?)",
                        [batch_id, r_hash, json.dumps(failed), raw, now])

        promoted = 0
        touched_orders: set[str] = set()
        if not halted:
            # Cross-batch exact-duplicate guard.
            existing = {h for (h,) in con.execute(
                "SELECT record_hash FROM silver.orders_events").fetchall()}
            for r_hash, rec in good:
                if r_hash in existing:
                    deduped += 1
                    continue
                con.execute(
                    "INSERT INTO silver.orders_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [batch_id, r_hash, rec["order_id"], rec["customer_id"],
                     rec["customer_name"], rec["order_ts"], rec["status"], rec["currency"],
                     rec["total_amount"],
                     json.dumps(rec["items"]) if rec["items"] is not None else None,
                     json.dumps(rec["extras"], ensure_ascii=False) if rec["extras"] else None,
                     now])
                promoted += 1
                touched_orders.add(rec["order_id"])

        if touched_orders:
            _rebuild_current(con, touched_orders)

        for name, count in rule_failures.items():
            severity = ruleset.severity_of(name)
            con.execute(
                "INSERT INTO meta.dq_results VALUES (?, 'silver', ?, ?, false, ?, ?, ?, ?)",
                [batch_id, name, severity, count, total,
                 f"fail_rate={fail_rate:.3f}", now])

        status = "quarantined" if halted else "promoted"
        con.execute("UPDATE meta.processed_batches SET status = ? WHERE batch_id = ?",
                    [status, batch_id])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    return {"batch_id": batch_id, "promoted": promoted if not halted else 0,
            "quarantined": len(quarantined), "deduped": deduped,
            "halted": halted, "fail_rate": round(fail_rate, 4)}


def _rebuild_current(con: duckdb.DuckDBPyConnection, order_ids: set[str]) -> None:
    """Recompute orders_current for the touched orders from the full event
    history — a pure function of orders_events, so replays converge."""
    ids = list(order_ids)
    con.execute("DELETE FROM silver.orders_current WHERE order_id IN (SELECT UNNEST(?))", [ids])
    con.execute("""
        INSERT INTO silver.orders_current
        SELECT order_id, customer_id, customer_name, order_ts, status, currency,
               total_amount, items, extras, promoted_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY order_id ORDER BY order_ts DESC, promoted_at DESC
            ) AS rn
            FROM silver.orders_events
            WHERE order_id IN (SELECT UNNEST(?))
        ) WHERE rn = 1
    """, [ids])
