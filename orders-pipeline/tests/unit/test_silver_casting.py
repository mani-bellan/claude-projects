"""Silver normalization: safe casts for drifted types, alias mapping, extras."""

from datetime import datetime, timezone

import pytest

from pipeline.silver import CastError, cast_amount, cast_timestamp, normalize
from tests.conftest import valid_order


class TestCastAmount:
    def test_float_passthrough(self):
        assert cast_amount(1234.5) == 1234.5

    def test_int_promotes(self):
        assert cast_amount(100) == 100.0

    def test_null_passthrough(self):
        assert cast_amount(None) is None

    def test_inr_symbol_and_commas(self):
        assert cast_amount("₹26,994.00") == 26994.0

    def test_plain_string_number(self):
        assert cast_amount("1,234.56") == 1234.56

    def test_negative_string(self):
        assert cast_amount("-500.00") == -500.0

    def test_garbage_raises(self):
        with pytest.raises(CastError):
            cast_amount("abc")

    def test_bool_raises(self):
        with pytest.raises(CastError):
            cast_amount(True)


class TestCastTimestamp:
    def test_iso_with_tz(self):
        ts = cast_timestamp("2026-07-06T12:00:00+00:00")
        assert ts == datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)

    def test_iso_without_tz_assumes_utc(self):
        assert cast_timestamp("2026-07-06T12:00:00").tzinfo == timezone.utc

    def test_drifted_ddmmyyyy_format(self):
        ts = cast_timestamp("06/07/2026 12:30")
        assert ts == datetime(2026, 7, 6, 12, 30, tzinfo=timezone.utc)

    def test_invalid_day_raises(self):
        with pytest.raises(CastError):
            cast_timestamp("45/13/2026 12:30")

    def test_garbage_raises(self):
        with pytest.raises(CastError):
            cast_timestamp("yesterday")

    def test_null_passthrough(self):
        assert cast_timestamp(None) is None


class TestNormalize:
    def test_clean_record_roundtrips(self):
        out = normalize(valid_order(order_id="ORD-X"), {})
        assert out["order_id"] == "ORD-X"
        assert out["total_amount"] == 2598.0
        assert out["extras"] is None

    def test_additive_columns_go_to_extras(self):
        out = normalize(valid_order(discount_code="X10", gift_wrap=True), {})
        assert out["extras"] == {"discount_code": "X10", "gift_wrap": True}

    def test_alias_restores_canonical_column(self):
        rec = valid_order()
        rec["cust_id"] = rec.pop("customer_id")
        out = normalize(rec, {"cust_id": "customer_id"})
        assert out["customer_id"] == "CUST-00042"
        assert out["extras"] is None

    def test_unaliased_rename_nulls_canonical_and_lands_in_extras(self):
        rec = valid_order()
        rec["cust_id"] = rec.pop("customer_id")
        out = normalize(rec, {})
        assert out["customer_id"] is None
        assert out["extras"] == {"cust_id": "CUST-00042"}

    def test_missing_column_fills_none(self):
        rec = valid_order()
        del rec["customer_name"]
        assert normalize(rec, {})["customer_name"] is None

    def test_unicode_survives(self):
        out = normalize(valid_order(customer_name="Ravi 🚀 Kumar"), {})
        assert out["customer_name"] == "Ravi 🚀 Kumar"
