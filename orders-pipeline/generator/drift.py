"""Schema drift engine.

Holds a mutable schema state and applies one of five drift modes, either
probabilistically or forced via CLI. State persists across runs in a JSON
sidecar so drift accumulates the way a real upstream system's would.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from generator import config

DRIFT_MODES = ["add_column", "remove_column", "type_change", "rename_column", "nested_drift"]


class DriftEngine:
    def __init__(self, state_path: Path, drift_probability: float = 0.15,
                 rng: random.Random | None = None):
        self.state_path = Path(state_path)
        self.drift_probability = drift_probability
        self.rng = rng or random.Random()
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {
            "schema_version": 1,
            "schema": dict(config.BASE_SCHEMA),
            "added": [],            # additive columns currently active
            "removed": [],          # base columns currently suppressed
            "renamed": {},          # canonical -> drifted name
            "type_changed": [],     # columns emitted as strings
            "nested_extra_keys": [],  # extra keys inside items[]
            "history": [],
        }

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2))
        tmp.rename(self.state_path)

    def maybe_drift(self, forced_mode: str | None = None) -> str | None:
        """Apply one drift mutation. Returns the mode applied, or None."""
        if forced_mode is None and self.rng.random() > self.drift_probability:
            return None
        mode = forced_mode or self.rng.choice(DRIFT_MODES)
        applied = getattr(self, f"_apply_{mode}")()
        if applied:
            self.state["schema_version"] += 1
            self.state["history"].append({"version": self.state["schema_version"], "mode": mode})
            return mode
        return None

    def revert_last(self) -> str | None:
        """Undo the most recent drift (for the 'drift that reverts' scenario)."""
        if not self.state["history"]:
            return None
        last = self.state["history"].pop()
        mode = last["mode"]
        if mode == "add_column" and self.state["added"]:
            self.state["added"].pop()
        elif mode == "remove_column" and self.state["removed"]:
            self.state["removed"].pop()
        elif mode == "rename_column" and self.state["renamed"]:
            self.state["renamed"].popitem()
        elif mode == "type_change" and self.state["type_changed"]:
            self.state["type_changed"].pop()
        elif mode == "nested_drift" and self.state["nested_extra_keys"]:
            self.state["nested_extra_keys"].pop()
        self.state["schema_version"] += 1
        self.state["history"].append({"version": self.state["schema_version"], "mode": f"revert_{mode}"})
        return mode

    # -- drift mode implementations; each returns True if it changed state --

    def _apply_add_column(self) -> bool:
        candidates = [c for c, _ in config.ADDITIVE_COLUMNS if c not in self.state["added"]]
        if not candidates:
            return False
        self.state["added"].append(candidates[0])
        return True

    def _apply_remove_column(self) -> bool:
        candidates = [c for c in config.REMOVABLE_COLUMNS if c not in self.state["removed"]]
        if not candidates:
            return False
        self.state["removed"].append(candidates[0])
        return True

    def _apply_type_change(self) -> bool:
        candidates = [c for c in ("total_amount", "order_ts") if c not in self.state["type_changed"]]
        if not candidates:
            return False
        self.state["type_changed"].append(candidates[0])
        return True

    def _apply_rename_column(self) -> bool:
        candidates = [(k, v) for k, v in config.RENAME_MAP.items()
                      if k not in self.state["renamed"] and k not in self.state["removed"]]
        if not candidates:
            return False
        k, v = candidates[0]
        self.state["renamed"][k] = v
        return True

    def _apply_nested_drift(self) -> bool:
        candidates = [k for k in ("warehouse_id", "estimated_ship_date") if k not in self.state["nested_extra_keys"]]
        if not candidates:
            return False
        self.state["nested_extra_keys"].append(candidates[0])
        return True

    # -- record shaping --

    def shape_record(self, record: dict) -> dict:
        """Apply the current drift state to a canonical record."""
        out = dict(record)
        for col in self.state["removed"]:
            out.pop(col, None)
        for col in self.state["type_changed"]:
            if col == "total_amount" and col in out and out[col] is not None:
                out[col] = f"₹{out[col]:,.2f}" if out.get("currency") == "INR" else f"{out[col]:,.2f}"
            elif col == "order_ts" and col in out:
                # ISO -> "DD/MM/YYYY HH:MM" format change
                ts = out[col]
                out[col] = f"{ts[8:10]}/{ts[5:7]}/{ts[0:4]} {ts[11:16]}"
        for canonical, drifted in self.state["renamed"].items():
            if canonical in out:
                out[drifted] = out.pop(canonical)
        for col in self.state["added"]:
            out[col] = self._additive_value(col)
        if self.state["nested_extra_keys"] and isinstance(out.get("items"), list):
            for item in out["items"]:
                for key in self.state["nested_extra_keys"]:
                    item[key] = self._nested_value(key)
        return out

    def _additive_value(self, col: str):
        if col == "discount_code":
            return self.rng.choice(config.DISCOUNT_CODES)
        if col == "shipping_tier":
            return self.rng.choice(config.SHIPPING_TIERS)
        if col == "gift_wrap":
            return self.rng.random() < 0.2
        if col == "loyalty_points":
            return self.rng.randint(0, 500)
        if col == "delivery_notes":
            return self.rng.choice(["Leave at door", "Call on arrival", None])
        return None

    def _nested_value(self, key: str):
        if key == "warehouse_id":
            return f"WH-{self.rng.randint(1, 9):02d}"
        if key == "estimated_ship_date":
            return "2026-07-10"
        return None
