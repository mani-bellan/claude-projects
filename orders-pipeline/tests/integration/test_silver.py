"""Silver promotion: dedup, upserts, quarantine, halt threshold, alias replay."""

from datetime import datetime, timedelta, timezone

from pipeline import warehouse
from pipeline.run import ingest, promote
from pipeline.schema_registry import register_alias
from tests.conftest import valid_order, write_batch_files

NOW = datetime.now(timezone.utc)


def land_and_load(paths, records, **kw):
    batch_id = write_batch_files(paths.incoming, records, **kw)
    ingest(paths)
    return batch_id


def q(paths, sql, params=None):
    con = warehouse.connect(paths.db_path)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


class TestPromotion:
    def test_clean_batch_promotes_fully(self, paths):
        b = land_and_load(paths, [valid_order() for _ in range(10)])
        result = promote(paths)[0]
        assert result == {"batch_id": b, "promoted": 10, "quarantined": 0,
                          "deduped": 0, "halted": False, "fail_rate": 0.0}
        assert q(paths, "SELECT COUNT(*) FROM silver.orders_current")[0][0] == 10

    def test_bad_rows_quarantined_with_rule_names(self, paths):
        records = [valid_order() for _ in range(8)]
        records.append(valid_order(order_id=None))
        records.append(valid_order(total_amount="not-a-number"))
        b = land_and_load(paths, records)
        result = promote(paths)[0]
        assert result["promoted"] == 8 and result["quarantined"] == 2
        failed = {r[0] for r in q(
            paths, "SELECT json_extract_string(failed_rules, '$[0]') FROM silver.quarantine")}
        assert failed == {"order_id_not_null", "uncastable_total_amount"}

    def test_quarantined_row_keeps_raw_payload(self, paths):
        land_and_load(paths, [valid_order(order_id=None, customer_name="Zoë")])
        promote(paths)
        raw = q(paths, "SELECT raw FROM silver.quarantine")[0][0]
        assert "Zoë" in raw

    def test_late_arrival_promotes(self, paths):
        late_ts = (NOW - timedelta(minutes=45)).isoformat()
        land_and_load(paths, [valid_order(order_ts=late_ts)])
        assert promote(paths)[0]["promoted"] == 1

    def test_future_ts_quarantined(self, paths):
        future = (NOW + timedelta(hours=6)).isoformat()
        land_and_load(paths, [valid_order(order_ts=future)])
        assert promote(paths)[0]["quarantined"] == 1

    def test_unicode_roundtrips_to_silver(self, paths):
        land_and_load(paths, [valid_order(customer_name="李小龙 🚀")])
        promote(paths)
        assert q(paths, "SELECT customer_name FROM silver.orders_current")[0][0] == "李小龙 🚀"


class TestDedupAndUpsert:
    def test_exact_duplicates_in_batch_deduped(self, paths):
        rec = valid_order()
        land_and_load(paths, [rec, rec, rec])
        result = promote(paths)[0]
        assert result["promoted"] == 1 and result["deduped"] == 2

    def test_exact_duplicate_across_batches_deduped(self, paths):
        rec = valid_order()
        land_and_load(paths, [rec])
        promote(paths)
        land_and_load(paths, [rec, valid_order()])
        result = promote(paths)[0]
        assert result["promoted"] == 1 and result["deduped"] == 1

    def test_status_update_wins_in_current_keeps_history(self, paths):
        rec = valid_order(status="placed")
        land_and_load(paths, [rec])
        promote(paths)
        shipped = dict(rec)
        shipped["status"] = "shipped"
        shipped["order_ts"] = (NOW + timedelta(minutes=2)).isoformat()
        land_and_load(paths, [shipped])
        promote(paths)
        assert q(paths, "SELECT status FROM silver.orders_current")[0][0] == "shipped"
        assert q(paths, "SELECT COUNT(*) FROM silver.orders_events")[0][0] == 2

    def test_out_of_order_events_latest_ts_still_wins(self, paths):
        rec = valid_order(status="delivered",
                          order_ts=(NOW - timedelta(minutes=1)).isoformat())
        older = dict(rec)
        older["status"] = "placed"
        older["order_ts"] = (NOW - timedelta(minutes=30)).isoformat()
        land_and_load(paths, [rec])  # newest arrives first
        promote(paths)
        land_and_load(paths, [older])  # older event arrives late
        promote(paths)
        assert q(paths, "SELECT status FROM silver.orders_current")[0][0] == "delivered"


class TestHaltThreshold:
    def test_exactly_at_threshold_does_not_halt(self, paths):
        records = [valid_order() for _ in range(8)] + \
                  [valid_order(order_id=None) for _ in range(2)]  # 20% bad
        land_and_load(paths, records)
        result = promote(paths)[0]
        assert result["halted"] is False and result["promoted"] == 8

    def test_above_threshold_halts_promotes_nothing(self, paths):
        records = [valid_order() for _ in range(7)] + \
                  [valid_order(order_id=None) for _ in range(3)]  # 30% bad
        b = land_and_load(paths, records)
        result = promote(paths)[0]
        assert result["halted"] is True and result["promoted"] == 0
        assert q(paths, "SELECT COUNT(*) FROM silver.orders_events")[0][0] == 0
        assert q(paths, "SELECT status FROM meta.processed_batches WHERE batch_id = ?",
                 [b])[0][0] == "quarantined"

    def test_fully_bad_batch_halts(self, paths):
        land_and_load(paths, [valid_order(status="bogus") for _ in range(5)])
        result = promote(paths)[0]
        assert result["halted"] is True and result["quarantined"] == 5

    def test_empty_batch_does_not_halt(self, paths):
        land_and_load(paths, [])
        result = promote(paths)[0]
        assert result["halted"] is False and result["fail_rate"] == 0.0


class TestIdempotentReplay:
    def test_re_promoting_same_batch_converges(self, paths):
        b = land_and_load(paths, [valid_order() for _ in range(6)])
        r1 = promote(paths, [b])[0]
        r2 = promote(paths, [b])[0]
        assert r1["promoted"] == r2["promoted"] == 6
        assert q(paths, "SELECT COUNT(*) FROM silver.orders_events")[0][0] == 6
        assert q(paths, "SELECT COUNT(*) FROM silver.orders_current")[0][0] == 6

    def test_rename_drift_healed_by_alias_then_replay(self, paths):
        rec = valid_order()
        rec["cust_id"] = rec.pop("customer_id")
        b = land_and_load(paths, [rec])
        promote(paths, [b])
        assert q(paths, "SELECT customer_id FROM silver.orders_current")[0][0] is None

        con = warehouse.connect(paths.db_path)
        register_alias(con, "cust_id", "customer_id")
        con.close()
        promote(paths, [b])  # replay through the same code path
        assert q(paths, "SELECT customer_id FROM silver.orders_current")[0][0] == "CUST-00042"
        assert q(paths, "SELECT COUNT(*) FROM silver.orders_events")[0][0] == 1
