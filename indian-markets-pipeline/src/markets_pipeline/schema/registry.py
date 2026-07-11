"""Persistent schema registry — tracks the declared schema of every table.

Stored as JSON next to the warehouse so schema state and data state can be
inspected together.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SchemaRegistry:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "tables": {}}
        return json.loads(self.path.read_text())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))

    # --- read --------------------------------------------------------------

    def get_table(self, name: str) -> dict[str, Any] | None:
        return self._data["tables"].get(name)

    def list_tables(self) -> list[str]:
        return sorted(self._data["tables"].keys())

    # --- write -------------------------------------------------------------

    def register_table(
        self,
        name: str,
        columns: dict[str, dict[str, Any]],
        primary_key: list[str],
    ) -> None:
        now = _now()
        self._data["tables"][name] = {
            "columns": columns,
            "primary_key": primary_key,
            "schema_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        self.save()

    def add_column(self, table: str, column: str, type_: str, nullable: bool = True) -> None:
        t = self._data["tables"][table]
        t["columns"][column] = {"type": type_, "nullable": nullable}
        t["schema_version"] += 1
        t["updated_at"] = _now()
        self.save()

    def update_column_type(self, table: str, column: str, new_type: str) -> None:
        t = self._data["tables"][table]
        t["columns"][column]["type"] = new_type
        t["schema_version"] += 1
        t["updated_at"] = _now()
        self.save()
