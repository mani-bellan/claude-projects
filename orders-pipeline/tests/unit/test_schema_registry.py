"""Schema inference and drift classification unit tests."""

import duckdb
import pytest

from pipeline import warehouse
from pipeline.schema_registry import (
    CANONICAL_COLUMNS, apply_aliases, classify, infer_schema,
    register_alias, register_batch_schema, schema_hash,
)
from tests.conftest import valid_order


@pytest.fixture
def con(tmp_path):
    c = warehouse.connect(tmp_path / "wh.duckdb")
    yield c
    c.close()


class TestInferSchema:
    def test_basic_types(self):
        s = infer_schema([valid_order()])
        assert s["order_id"] == "string"
        assert s["total_amount"] == "float"
        assert s["items"] == "array"

    def test_null_does_not_mask_type(self):
        s = infer_schema([{"a": None}, {"a": "x"}])
        assert s["a"] == "string"

    def test_all_null_column_stays_null(self):
        assert infer_schema([{"a": None}])["a"] == "null"

    def test_int_float_promotes_not_mixed(self):
        assert infer_schema([{"a": 1}, {"a": 1.5}])["a"] == "float"

    def test_conflicting_types_are_mixed(self):
        assert infer_schema([{"a": 1}, {"a": "x"}])["a"] == "mixed"

    def test_hash_independent_of_key_order(self):
        assert schema_hash({"a": "string", "b": "float"}) == \
            schema_hash({"b": "float", "a": "string"})


class TestClassify:
    def _cls(self, records, aliases=None):
        return classify(infer_schema(records), CANONICAL_COLUMNS, aliases or {})

    def test_baseline(self):
        assert self._cls([valid_order()]).classification == "baseline"

    def test_additive(self):
        report = self._cls([valid_order(discount_code="X10")])
        assert report.classification == "additive"
        assert report.added == ["discount_code"]

    def test_column_removed(self):
        rec = valid_order()
        del rec["customer_name"]
        report = self._cls([rec])
        assert report.classification == "column_removed"
        assert report.removed == ["customer_name"]

    def test_type_change(self):
        report = self._cls([valid_order(total_amount="₹1,299.00")])
        assert report.classification == "type_change"
        assert report.type_changed == ["total_amount"]

    def test_int_amount_is_not_type_change(self):
        assert self._cls([valid_order(total_amount=100)]).classification == "baseline"

    def test_rename_without_alias_is_unknown(self):
        rec = valid_order()
        rec["cust_id"] = rec.pop("customer_id")
        report = self._cls([rec])
        assert report.classification == "unknown"
        assert report.added == ["cust_id"]
        assert report.removed == ["customer_id"]

    def test_rename_with_alias_is_baseline(self):
        rec = valid_order()
        rec["cust_id"] = rec.pop("customer_id")
        report = self._cls([rec], aliases={"cust_id": "customer_id"})
        assert report.classification == "baseline"

    def test_multiple_drifts_worst_wins(self):
        rec = valid_order(total_amount="₹1.00", gift_wrap=True)
        del rec["customer_name"]
        report = self._cls([rec])
        assert report.classification == "type_change"
        assert report.added == ["gift_wrap"]
        assert report.removed == ["customer_name"]


class TestAliases:
    def test_apply_aliases_maps_and_keeps_canonical_on_clash(self):
        out = apply_aliases({"cust_id": "A", "customer_id": "B"},
                            {"cust_id": "customer_id"})
        assert out["customer_id"] == "B"

    def test_register_alias_rejects_unknown_canonical(self, con):
        with pytest.raises(ValueError):
            register_alias(con, "foo", "not_a_column")

    def test_alias_roundtrip_via_registry_table(self, con):
        register_alias(con, "cust_id", "customer_id")
        out = apply_aliases({"cust_id": "A"},
                            dict(con.execute("SELECT * FROM meta.column_aliases").fetchall()))
        assert out == {"customer_id": "A"}


class TestRegistryPersistence:
    def test_new_schema_registered_once(self, con):
        records = [valid_order()]
        r1 = register_batch_schema(con, "b1", records)
        r2 = register_batch_schema(con, "b2", records)
        assert r1.is_new and not r2.is_new
        count = con.execute("SELECT COUNT(*) FROM meta.schema_registry").fetchone()[0]
        assert count == 1

    def test_drifted_schema_gets_own_entry(self, con):
        register_batch_schema(con, "b1", [valid_order()])
        register_batch_schema(con, "b2", [valid_order(gift_wrap=True)])
        rows = con.execute(
            "SELECT classification FROM meta.schema_registry ORDER BY first_seen_at").fetchall()
        assert [r[0] for r in rows] == ["baseline", "additive"]
