"""Shared fixtures: temp warehouse, landing zone, record/batch factories."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dq.runner import RuleSet  # noqa: E402
from pipeline.run import Paths  # noqa: E402


@pytest.fixture
def paths(tmp_path) -> Paths:
    return Paths(db_path=tmp_path / "wh.duckdb", landing_root=tmp_path / "landing")


@pytest.fixture
def ruleset() -> RuleSet:
    return RuleSet.load()


def valid_order(**overrides) -> dict:
    """Canonical, DQ-clean order record."""
    rec = {
        "order_id": f"ORD-{uuid.uuid4().hex[:12]}",
        "customer_id": "CUST-00042",
        "customer_name": "Priya Iyer",
        "order_ts": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "status": "placed",
        "currency": "INR",
        "total_amount": 2598.0,
        "items": [{"sku": "SKU-1001", "name": "Wireless Mouse", "qty": 2, "unit_price": 1299.0}],
    }
    rec.update(overrides)
    return rec


def write_batch_files(incoming: Path, records: list[dict], batch_id: str | None = None,
                      tamper: str | None = None) -> str:
    """Write a data+manifest pair. tamper: checksum | row_count | corrupt_json |
    no_manifest | whitespace. Returns batch_id."""
    incoming.mkdir(parents=True, exist_ok=True)
    batch_id = batch_id or uuid.uuid4().hex[:16]
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    stem = f"orders_{batch_id}_{ts_tag}"

    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    if records:
        payload += "\n"
    row_count = len(records)

    if tamper == "corrupt_json":
        payload += '{"order_id": "ORD-broken", not valid json\n'
        row_count += 1  # manifest expects the broken line to be a record
    elif tamper == "whitespace":
        payload = "   \n\n  \n"
        row_count = 0

    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if tamper == "checksum":
        sha = "0" * 64
    if tamper == "row_count":
        row_count += 5

    (incoming / f"{stem}.jsonl").write_text(payload, encoding="utf-8")
    if tamper != "no_manifest":
        manifest = {"batch_id": batch_id, "row_count": row_count, "sha256": sha,
                    "schema_version": 1,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "data_file": f"{stem}.jsonl"}
        (incoming / f"{stem}.manifest.json").write_text(json.dumps(manifest))
    return batch_id
