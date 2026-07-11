"""Generator unit tests: drift modes, atomic writes, manifests, realism knobs."""

import json
import random
from pathlib import Path

import pytest

from generator.drift import DriftEngine, DRIFT_MODES
from generator.generate import generate_batch


@pytest.fixture
def state_path(tmp_path) -> Path:
    return tmp_path / "state.json"


class TestDriftEngine:
    def test_no_drift_below_probability(self, state_path):
        engine = DriftEngine(state_path, drift_probability=0.0)
        assert engine.maybe_drift() is None
        assert engine.state["schema_version"] == 1

    @pytest.mark.parametrize("mode", DRIFT_MODES)
    def test_each_forced_mode_mutates_exactly_its_target(self, state_path, mode):
        engine = DriftEngine(state_path)
        applied = engine.maybe_drift(forced_mode=mode)
        assert applied == mode
        assert engine.state["schema_version"] == 2
        state = engine.state
        touched = {
            "add_column": bool(state["added"]),
            "remove_column": bool(state["removed"]),
            "type_change": bool(state["type_changed"]),
            "rename_column": bool(state["renamed"]),
            "nested_drift": bool(state["nested_extra_keys"]),
        }
        assert touched.pop(mode) is True
        assert not any(touched.values()), "other drift dimensions must be untouched"

    def test_add_column_shapes_records(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="add_column")
        rec = engine.shape_record({"order_id": "X", "items": []})
        assert "discount_code" in rec

    def test_remove_column_drops_field(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="remove_column")
        rec = engine.shape_record({"order_id": "X", "customer_name": "A", "items": []})
        assert "customer_name" not in rec

    def test_type_change_stringifies_amount(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="type_change")
        rec = engine.shape_record(
            {"order_id": "X", "total_amount": 1234.5, "currency": "INR", "items": []})
        assert isinstance(rec["total_amount"], str)
        assert "1,234.50" in rec["total_amount"]

    def test_rename_moves_value(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="rename_column")
        rec = engine.shape_record({"order_id": "X", "customer_id": "C1", "items": []})
        assert "customer_id" not in rec
        assert rec["cust_id"] == "C1"

    def test_nested_drift_adds_item_keys(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="nested_drift")
        rec = engine.shape_record({"order_id": "X", "items": [{"sku": "S1"}]})
        assert "warehouse_id" in rec["items"][0]

    def test_drift_accumulates_and_persists(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="add_column")
        engine.maybe_drift(forced_mode="remove_column")
        engine.save()
        reloaded = DriftEngine(state_path)
        assert reloaded.state["schema_version"] == 3
        assert reloaded.state["added"] and reloaded.state["removed"]

    def test_revert_last_undoes_drift(self, state_path):
        engine = DriftEngine(state_path)
        engine.maybe_drift(forced_mode="add_column")
        assert engine.revert_last() == "add_column"
        rec = engine.shape_record({"order_id": "X", "items": []})
        assert "discount_code" not in rec

    def test_exhausted_mode_returns_none(self, state_path):
        engine = DriftEngine(state_path)
        for _ in range(len(["total_amount", "order_ts"])):
            engine.maybe_drift(forced_mode="type_change")
        assert engine.maybe_drift(forced_mode="type_change") is None


class TestGenerateBatch:
    def test_batch_files_and_manifest_consistent(self, tmp_path, state_path):
        result = generate_batch(tmp_path / "in", state_path, rows=20, seed=7,
                                drift_probability=0.0)
        assert result["rows"] == 20
        data = Path(result["data_file"])
        lines = [json.loads(l) for l in data.read_text(encoding="utf-8").splitlines()]
        assert len(lines) == 20
        manifest = json.loads(
            data.with_name(data.name.replace(".jsonl", ".manifest.json")).read_text())
        assert manifest["row_count"] == 20
        assert manifest["batch_id"] == result["batch_id"]

    def test_no_partial_files_left_behind(self, tmp_path, state_path):
        generate_batch(tmp_path / "in", state_path, rows=5, seed=1)
        leftovers = list((tmp_path / "in").glob("*.tmp"))
        assert leftovers == []

    def test_forced_drift_reflected_in_records(self, tmp_path, state_path):
        result = generate_batch(tmp_path / "in", state_path, rows=10, seed=3,
                                force_drift="add_column")
        assert result["drift_applied"] == "add_column"
        lines = [json.loads(l) for l in
                 Path(result["data_file"]).read_text(encoding="utf-8").splitlines()]
        assert all("discount_code" in r for r in lines)

    def test_seeded_content_is_deterministic(self, tmp_path, state_path):
        r1 = generate_batch(tmp_path / "a", tmp_path / "s1.json", rows=15, seed=99,
                            drift_probability=0.0)
        r2 = generate_batch(tmp_path / "b", tmp_path / "s2.json", rows=15, seed=99,
                            drift_probability=0.0)
        # order_id is uuid4 and order_ts derives from wall-clock, so neither
        # is seed-determined; everything else must match exactly
        strip = lambda p: [
            {k: v for k, v in json.loads(l).items() if k not in ("order_id", "order_ts")}
            for l in Path(p).read_text(encoding="utf-8").splitlines()]
        assert strip(r1["data_file"]) == strip(r2["data_file"])

    def test_realism_knobs_present_in_large_seeded_batch(self, tmp_path, state_path):
        result = generate_batch(tmp_path / "in", state_path, rows=500, seed=11,
                                drift_probability=0.0)
        recs = [json.loads(l) for l in
                Path(result["data_file"]).read_text(encoding="utf-8").splitlines()]
        order_ids = [r["order_id"] for r in recs]
        assert len(set(order_ids)) < len(order_ids), "expected duplicate order events"
        assert any(r["customer_name"] is None for r in recs), "expected null names"
        assert any(r["total_amount"] < 0 for r in recs), "expected negative amounts"
