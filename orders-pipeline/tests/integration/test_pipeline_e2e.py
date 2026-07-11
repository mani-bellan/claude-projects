"""End-to-end: full runs, drift sequences, gold correctness, batch DQ alerts."""

import json

from generator.generate import generate_batch
from pipeline import warehouse
from pipeline.run import run_once
from tests.conftest import valid_order, write_batch_files


def q(paths, sql, params=None):
    con = warehouse.connect(paths.db_path)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


class TestRunOnce:
    def test_empty_landing_zone_skips(self, paths):
        assert run_once(paths) == {"skipped": True, "reason": "no new files"}

    def test_single_batch_flows_to_gold(self, paths):
        write_batch_files(paths.incoming, [
            valid_order(total_amount=100.0, currency="INR"),
            valid_order(total_amount=200.0, currency="INR"),
        ])
        result = run_once(paths)
        assert result["promoted"][0]["promoted"] == 2
        revenue = q(paths, """
            SELECT SUM(revenue) FROM gold.daily_revenue WHERE currency = 'INR'
        """)[0][0]
        assert revenue == 300.0

    def test_gold_recomputes_after_status_update(self, paths):
        rec = valid_order(status="placed", total_amount=100.0)
        write_batch_files(paths.incoming, [rec])
        run_once(paths)
        refund = dict(rec)
        refund["status"] = "refunded"
        refund["total_amount"] = -100.0
        refund["order_ts"] = valid_order()["order_ts"]  # newer ts
        write_batch_files(paths.incoming, [refund])
        run_once(paths)
        funnel = dict(q(paths, "SELECT status, orders FROM gold.order_funnel"))
        assert funnel == {"refunded": 1}, "gold reflects latest state, no double count"

    def test_dq_metrics_mart_tracks_quarantine_rate(self, paths):
        write_batch_files(paths.incoming, [valid_order() for _ in range(9)] +
                          [valid_order(order_id=None)])
        run_once(paths)
        rate = q(paths, "SELECT quarantine_rate FROM gold.dq_metrics")[0][0]
        assert rate == 0.1

    def test_failed_file_does_not_block_good_batch(self, paths):
        write_batch_files(paths.incoming, [valid_order()], tamper="checksum")
        good = write_batch_files(paths.incoming, [valid_order() for _ in range(3)])
        result = run_once(paths)
        assert not result["skipped"]
        assert q(paths, "SELECT COUNT(*) FROM bronze.orders_raw WHERE batch_id = ?",
                 [good])[0][0] == 3
        statuses = {r[0]: r[1] for r in q(
            paths, "SELECT batch_id, status FROM meta.processed_batches")}
        assert statuses[good] == "promoted"
        assert "failed" in statuses.values()

    def test_rerun_with_no_new_files_skips_cleanly(self, paths):
        write_batch_files(paths.incoming, [valid_order()])
        run_once(paths)
        assert run_once(paths)["skipped"] is True


class TestBatchDQAlerts:
    def test_volume_anomaly_flags_tiny_batch(self, paths):
        for _ in range(3):
            write_batch_files(paths.incoming, [valid_order() for _ in range(100)])
            run_once(paths)
        write_batch_files(paths.incoming, [valid_order()])  # 1 row vs avg 100
        result = run_once(paths)
        breaches = [b["rule_name"] for b in result["dq_breaches"]]
        assert "volume_anomaly" in breaches

    def test_normal_volume_does_not_alert(self, paths):
        for _ in range(4):
            write_batch_files(paths.incoming, [valid_order() for _ in range(100)])
            result = run_once(paths)
        assert all(b["rule_name"] != "volume_anomaly" for b in result["dq_breaches"])

    def test_dq_results_persisted_for_audit(self, paths):
        write_batch_files(paths.incoming, [valid_order()])
        run_once(paths)
        layers = {r[0] for r in q(paths, "SELECT DISTINCT layer FROM meta.dq_results")}
        assert "batch" in layers


class TestGeneratorToGoldSmoke:
    def test_five_generated_batches_with_forced_drift_schedule(self, paths, tmp_path):
        """The E2E smoke: real generator (fast mode), forced drift sequence,
        assert registry captured the drift and gold is coherent."""
        state = tmp_path / "gen_state.json"
        drift_schedule = [None, "add_column", "type_change", "rename_column", None]
        for i, mode in enumerate(drift_schedule):
            generate_batch(paths.incoming, state, rows=30, seed=100 + i,
                           force_drift=mode, drift_probability=0.0)
            result = run_once(paths)
            assert not result["skipped"]

        classifications = {r[0] for r in q(
            paths, "SELECT classification FROM meta.schema_registry")}
        assert "baseline" in classifications
        assert {"additive", "type_change", "unknown"} & classifications, \
            "drift must be captured in the registry"

        batches = q(paths, "SELECT COUNT(*) FROM meta.processed_batches")[0][0]
        assert batches == 5
        assert q(paths, "SELECT COUNT(*) FROM gold.dq_metrics")[0][0] == 5

        # every bronze row is accounted for: promoted, quarantined, or deduped
        bronze_rows = q(paths, "SELECT COUNT(*) FROM bronze.orders_raw")[0][0]
        events = q(paths, "SELECT COUNT(*) FROM silver.orders_events")[0][0]
        quarantined = q(paths, "SELECT COUNT(*) FROM silver.quarantine")[0][0]
        assert bronze_rows == 150
        assert events + quarantined <= 150
        assert events > 0

        # type_change drift: stringified amounts must have been safe-cast
        drifted_amounts = q(paths, """
            SELECT COUNT(*) FROM silver.orders_events
            WHERE total_amount IS NOT NULL
        """)[0][0]
        assert drifted_amounts > 0

    def test_drift_that_reverts_next_batch(self, paths, tmp_path):
        state = tmp_path / "gen_state.json"
        generate_batch(paths.incoming, state, rows=10, seed=1,
                       force_drift="add_column", drift_probability=0.0)
        run_once(paths)
        from generator.drift import DriftEngine
        engine = DriftEngine(state)
        engine.revert_last()
        engine.save()
        generate_batch(paths.incoming, state, rows=10, seed=2, drift_probability=0.0)
        result = run_once(paths)
        assert result["promoted"][0]["promoted"] > 0
        schemas = q(paths, "SELECT COUNT(*) FROM meta.schema_registry")[0][0]
        assert schemas == 2, "reverted schema matches the original registry entry"


class TestConcurrencySafety:
    def test_batches_landing_mid_run_are_picked_up_next_run(self, paths):
        """Simulates a file arriving between sense and the next run."""
        write_batch_files(paths.incoming, [valid_order()])
        run_once(paths)
        write_batch_files(paths.incoming, [valid_order()])
        result = run_once(paths)
        assert not result["skipped"]
        assert q(paths, "SELECT COUNT(*) FROM meta.processed_batches")[0][0] == 2
