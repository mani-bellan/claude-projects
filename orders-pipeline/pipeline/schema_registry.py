"""Schema inference, drift classification, and the registry.

Bronze always succeeds; this module only *classifies* what changed so silver
can decide how to promote. Classifications:

  baseline        first schema ever seen
  additive        new column(s) only -> auto-evolve
  column_removed  column(s) gone -> proceed, silver fills NULL
  type_change     observed JSON type changed for a known column -> safe-cast in silver
  unknown         anything else / mixed breaking changes -> quarantine-prone, warn loudly
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import duckdb

# Canonical silver columns (typed). Everything else observed goes to extras.
CANONICAL_COLUMNS = {
    "order_id": "string",
    "customer_id": "string",
    "customer_name": "string",
    "order_ts": "timestamp",
    "status": "string",
    "currency": "string",
    "total_amount": "float",
    "items": "array",
}

_JSON_TYPES = {str: "string", bool: "boolean", int: "integer", float: "float",
               list: "array", dict: "object", type(None): "null"}


def infer_schema(records: list[dict]) -> dict[str, str]:
    """Column -> observed type, unioned across records. Nulls don't mask types."""
    schema: dict[str, str] = {}
    for r in records:
        for k, v in r.items():
            t = _JSON_TYPES.get(type(v), "string")
            if k not in schema or schema[k] == "null":
                schema[k] = t
            elif t != "null" and schema[k] != t:
                # int/float promotion is not drift; anything else is a mixed column
                if {schema[k], t} == {"integer", "float"}:
                    schema[k] = "float"
                else:
                    schema[k] = "mixed"
    return schema


def schema_hash(schema: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class DriftReport:
    schema: dict[str, str]
    hash: str
    classification: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    type_changed: list[str] = field(default_factory=list)
    is_new: bool = True

    def to_changes_json(self) -> str:
        return json.dumps({"added": self.added, "removed": self.removed,
                           "type_changed": self.type_changed})


def load_aliases(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    rows = con.execute("SELECT alias_name, canonical_name FROM meta.column_aliases").fetchall()
    return dict(rows)


def register_alias(con: duckdb.DuckDBPyConnection, alias: str, canonical: str) -> None:
    if canonical not in CANONICAL_COLUMNS:
        raise ValueError(f"{canonical!r} is not a canonical column")
    con.execute(
        "INSERT OR REPLACE INTO meta.column_aliases VALUES (?, ?)", [alias, canonical])


def apply_aliases(record: dict, aliases: dict[str, str]) -> dict:
    """Map drifted names back to canonical ones (canonical value wins on clash)."""
    out = {k: v for k, v in record.items() if k not in aliases}
    for k, v in record.items():
        if k in aliases and aliases[k] not in out:
            out[aliases[k]] = v
    return out


def classify(observed: dict[str, str], reference: dict[str, str],
             aliases: dict[str, str]) -> DriftReport:
    """Compare an observed schema (post-alias) against the canonical reference."""
    # Compare in JSON-type space: a timestamp arrives over the wire as a
    # string, so its expected observed type is "string" (format drift within
    # strings is the silver caster's problem, not a schema change).
    expected = {k: ("string" if v == "timestamp" else v) for k, v in reference.items()}
    normalized = {aliases.get(k, k): v for k, v in observed.items()}
    added = sorted(k for k in normalized if k not in expected)
    removed = sorted(k for k in expected if k not in normalized)
    type_changed = sorted(
        k for k in normalized
        if k in expected and normalized[k] not in (expected[k], "null")
        and not (expected[k] == "float" and normalized[k] == "integer"))

    if not added and not removed and not type_changed:
        classification = "baseline"
    elif type_changed:
        classification = "type_change"
    elif added and removed:
        # possible rename: same count, unknown mapping -> needs an alias
        classification = "unknown"
    elif added:
        classification = "additive"
    else:
        classification = "column_removed"

    return DriftReport(schema=observed, hash=schema_hash(observed),
                       classification=classification, added=added,
                       removed=removed, type_changed=type_changed)


def register_batch_schema(con: duckdb.DuckDBPyConnection, batch_id: str,
                          records: list[dict]) -> DriftReport:
    """Infer, classify vs canonical, and persist if never seen before."""
    aliases = load_aliases(con)
    observed = infer_schema(records)
    report = classify(observed, CANONICAL_COLUMNS, aliases)

    seen = con.execute(
        "SELECT 1 FROM meta.schema_registry WHERE schema_hash = ?", [report.hash]).fetchone()
    report.is_new = seen is None
    if report.is_new:
        con.execute(
            "INSERT INTO meta.schema_registry VALUES (?, ?, ?, ?, ?, ?)",
            [report.hash, json.dumps(observed), datetime.now(timezone.utc),
             batch_id, report.classification, report.to_changes_json()])
    return report
