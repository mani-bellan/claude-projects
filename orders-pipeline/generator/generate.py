"""E-commerce order batch generator.

Writes one JSONL batch + manifest sidecar to the landing zone per invocation.
Atomic writes (tmp -> rename) guarantee the pipeline never sees partial files.

Usage:
    python -m generator.generate --landing warehouse/landing/incoming
    python -m generator.generate --force-drift add_column --rows 50
    python -m generator.generate --loop --interval 5          # fast mode for E2E tests
    python -m generator.generate --revert-drift
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from generator import config
from generator.drift import DriftEngine, DRIFT_MODES

WINDOW_MINUTES = 15


def make_order(rng: random.Random, now: datetime, emitted: list[dict]) -> dict:
    """Build one canonical order record, with realism knobs applied."""
    # Duplicate-event knob: re-emit a prior order with a later status.
    if emitted and rng.random() < config.DUPLICATE_EVENT_RATE:
        prev = rng.choice(emitted)
        idx = config.STATUSES.index(prev["status"])
        if idx < len(config.STATUSES) - 1:
            dup = dict(prev)
            dup["status"] = config.STATUSES[min(idx + 1, 3)]  # advance toward delivered
            dup["order_ts"] = now.isoformat()
            dup["items"] = [dict(i) for i in prev["items"]]
            return dup

    ts = now - timedelta(seconds=rng.randint(0, WINDOW_MINUTES * 60))
    if rng.random() < config.LATE_ARRIVAL_RATE:
        ts -= timedelta(minutes=WINDOW_MINUTES * rng.randint(1, 3))
    elif rng.random() < config.FUTURE_TS_RATE:
        ts += timedelta(hours=rng.randint(1, 48))

    status = rng.choices(config.STATUSES, weights=[35, 25, 15, 15, 5, 5])[0]
    n_items = rng.randint(1, 4)
    items = []
    for _ in range(n_items):
        p = rng.choice(config.PRODUCTS)
        qty = rng.randint(1, 3)
        items.append({"sku": p["sku"], "name": p["name"], "qty": qty, "unit_price": p["unit_price"]})
    total = round(sum(i["qty"] * i["unit_price"] for i in items), 2)
    if status == "refunded" and rng.random() < 0.9:
        total = -total  # legit negative
    elif rng.random() < config.NEGATIVE_AMOUNT_RATE:
        total = -abs(total)  # bad data: negative on a non-refund

    currency = rng.choice(config.CURRENCIES)
    if rng.random() < config.BAD_CURRENCY_RATE:
        currency = rng.choice(["XXX", "RUPEE", ""])

    name = rng.choice(config.CUSTOMER_NAMES)
    if rng.random() < config.NULL_OPTIONAL_RATE:
        name = None

    return {
        "order_id": f"ORD-{uuid.uuid4().hex[:12]}",
        "customer_id": f"CUST-{rng.randint(1, 500):05d}",
        "customer_name": name,
        "order_ts": ts.isoformat(),
        "status": status,
        "currency": currency,
        "total_amount": total,
        "items": items,
    }


def write_batch(landing_dir: Path, records: list[dict], batch_id: str,
                schema_version: int) -> tuple[Path, Path]:
    """Atomically write batch JSONL + manifest. Returns (data_path, manifest_path)."""
    landing_dir.mkdir(parents=True, exist_ok=True)
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    stem = f"orders_{batch_id}_{ts_tag}"
    data_path = landing_dir / f"{stem}.jsonl"
    manifest_path = landing_dir / f"{stem}.manifest.json"

    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    if records:
        payload += "\n"
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    tmp_data = data_path.with_suffix(".jsonl.tmp")
    tmp_data.write_text(payload, encoding="utf-8")
    tmp_data.rename(data_path)

    manifest = {
        "batch_id": batch_id,
        "row_count": len(records),
        "sha256": checksum,
        "schema_version": schema_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_file": data_path.name,
    }
    tmp_man = manifest_path.with_suffix(".json.tmp")
    tmp_man.write_text(json.dumps(manifest, indent=2))
    tmp_man.rename(manifest_path)
    return data_path, manifest_path


def generate_batch(landing_dir: Path, state_path: Path, rows: int | None = None,
                   force_drift: str | None = None, drift_probability: float = 0.15,
                   seed: int | None = None) -> dict:
    """Generate one batch. Returns the manifest dict."""
    rng = random.Random(seed)
    engine = DriftEngine(state_path, drift_probability=drift_probability, rng=rng)
    drift_applied = engine.maybe_drift(forced_mode=force_drift)

    now = datetime.now(timezone.utc)
    n = rows if rows is not None else rng.randint(*config.DEFAULT_ROWS_PER_BATCH)
    canonical: list[dict] = []
    for _ in range(n):
        canonical.append(make_order(rng, now, canonical))
    shaped = [engine.shape_record(r) for r in canonical]

    batch_id = uuid.uuid4().hex[:16]
    data_path, manifest_path = write_batch(
        landing_dir, shaped, batch_id, engine.state["schema_version"])
    engine.save()
    return {
        "batch_id": batch_id,
        "rows": len(shaped),
        "drift_applied": drift_applied,
        "schema_version": engine.state["schema_version"],
        "data_file": str(data_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate e-commerce order batches")
    parser.add_argument("--landing", default="warehouse/landing/incoming")
    parser.add_argument("--state", default="warehouse/generator_state.json")
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--force-drift", choices=DRIFT_MODES, default=None)
    parser.add_argument("--revert-drift", action="store_true")
    parser.add_argument("--drift-probability", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=float, default=WINDOW_MINUTES * 60,
                        help="seconds between batches in --loop mode")
    args = parser.parse_args()

    landing = Path(args.landing)
    state = Path(args.state)

    if args.revert_drift:
        engine = DriftEngine(state)
        mode = engine.revert_last()
        engine.save()
        print(f"reverted drift: {mode}")
        return

    while True:
        result = generate_batch(landing, state, rows=args.rows,
                                force_drift=args.force_drift,
                                drift_probability=args.drift_probability,
                                seed=args.seed)
        print(json.dumps(result))
        if not args.loop:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
