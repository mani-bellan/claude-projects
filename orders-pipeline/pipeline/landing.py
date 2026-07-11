"""Landing zone operations: discovery, manifest verification, file lifecycle."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

FILENAME_RE = re.compile(r"^orders_(?P<batch_id>[0-9a-f]+)_(?P<ts>\d{8}T\d{6})\.jsonl$")


class LandingError(Exception):
    """Batch-level failure: file unusable, manifest mismatch, etc."""


@dataclass
class Batch:
    batch_id: str
    data_path: Path
    manifest_path: Path
    manifest: dict


def discover_batches(incoming_dir: Path) -> list[Batch]:
    """Find complete (data + manifest) batches, oldest first.

    Files without a matching manifest yet are skipped, not failed — the
    generator writes data first, so a lone data file may just be mid-batch.
    """
    incoming_dir = Path(incoming_dir)
    if not incoming_dir.exists():
        return []
    batches = []
    for data_path in sorted(incoming_dir.glob("orders_*.jsonl")):
        m = FILENAME_RE.match(data_path.name)
        if not m:
            continue
        manifest_path = data_path.with_name(data_path.name.replace(".jsonl", ".manifest.json"))
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        batches.append(Batch(m.group("batch_id"), data_path, manifest_path, manifest))
    return batches


def read_and_verify(batch: Batch) -> list[dict]:
    """Read records, verifying checksum and row count against the manifest."""
    payload = batch.data_path.read_text(encoding="utf-8")
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if checksum != batch.manifest.get("sha256"):
        raise LandingError(f"checksum mismatch for {batch.data_path.name}")

    records = []
    for lineno, line in enumerate(payload.splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise LandingError(f"corrupt JSON at {batch.data_path.name}:{lineno}: {e}") from e

    expected = batch.manifest.get("row_count")
    if expected is not None and len(records) != expected:
        raise LandingError(
            f"row count mismatch for {batch.data_path.name}: manifest={expected} actual={len(records)}")
    return records


def archive_batch(batch: Batch, dest_dir: Path) -> None:
    """Move a batch's files out of incoming/ (to processed/ or failed/)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for p in (batch.data_path, batch.manifest_path):
        if p.exists():
            p.rename(dest_dir / p.name)


def record_hash(record: dict) -> str:
    """Stable content hash for dedup (independent of key order)."""
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
