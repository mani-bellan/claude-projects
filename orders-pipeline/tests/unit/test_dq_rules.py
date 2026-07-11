"""Every DQ row rule: pass, fail, and boundary. Batch rules tested in integration."""

from datetime import datetime, timedelta, timezone

import pytest

from dq.runner import RuleSet

NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def rules() -> RuleSet:
    return RuleSet.load()


def normalized(**overrides) -> dict:
    """A DQ-clean normalized record (post-cast, canonical shape)."""
    rec = {
        "order_id": "ORD-1", "customer_id": "CUST-1", "customer_name": "Priya",
        "order_ts": NOW - timedelta(minutes=10), "status": "placed",
        "currency": "INR", "total_amount": 100.0,
        "items": [{"sku": "S1", "qty": 1}], "extras": None,
    }
    rec.update(overrides)
    return rec


def failures(rules, **overrides):
    return rules.evaluate_row(normalized(**overrides), now=NOW)


class TestCleanRecord:
    def test_clean_record_passes_all_rules(self, rules):
        assert failures(rules) == []


class TestNotNull:
    def test_null_order_id(self, rules):
        assert "order_id_not_null" in failures(rules, order_id=None)

    def test_null_order_ts(self, rules):
        assert "order_ts_not_null" in failures(rules, order_ts=None)


class TestInSet:
    def test_bad_status(self, rules):
        assert "status_in_allowed_set" in failures(rules, status="teleported")

    def test_null_status_fails(self, rules):
        assert "status_in_allowed_set" in failures(rules, status=None)

    def test_bad_currency(self, rules):
        assert "currency_iso_valid" in failures(rules, currency="RUPEE")

    def test_empty_currency_fails(self, rules):
        assert "currency_iso_valid" in failures(rules, currency="")

    def test_null_currency_allowed(self, rules):
        # column-removal drift must not quarantine: currency allows null
        assert "currency_iso_valid" not in failures(rules, currency=None)


class TestRange:
    def test_amount_above_bound(self, rules):
        assert "amount_within_bounds" in failures(rules, total_amount=2_000_000.0)

    def test_amount_exactly_at_bound_passes(self, rules):
        assert "amount_within_bounds" not in failures(rules, total_amount=1_000_000.0)

    def test_null_amount_allowed(self, rules):
        assert "amount_within_bounds" not in failures(rules, total_amount=None)


class TestTimestamps:
    def test_future_ts_fails(self, rules):
        assert "order_ts_not_future" in failures(
            rules, order_ts=NOW + timedelta(hours=2))

    def test_ts_within_tolerance_passes(self, rules):
        assert "order_ts_not_future" not in failures(
            rules, order_ts=NOW + timedelta(minutes=4))

    def test_ts_just_past_tolerance_fails(self, rules):
        assert "order_ts_not_future" in failures(
            rules, order_ts=NOW + timedelta(minutes=6))

    def test_late_arrival_within_window_passes(self, rules):
        assert "order_ts_not_stale" not in failures(
            rules, order_ts=NOW - timedelta(minutes=45))

    def test_stale_ts_fails(self, rules):
        assert "order_ts_not_stale" in failures(
            rules, order_ts=NOW - timedelta(days=31))

    def test_exactly_30_days_passes(self, rules):
        assert "order_ts_not_stale" not in failures(
            rules, order_ts=NOW - timedelta(days=30))


class TestNegativeAmounts:
    def test_negative_on_refund_passes(self, rules):
        assert "negative_amount_only_refunds" not in failures(
            rules, status="refunded", total_amount=-500.0)

    def test_negative_on_placed_fails(self, rules):
        assert "negative_amount_only_refunds" in failures(
            rules, status="placed", total_amount=-500.0)

    def test_zero_amount_passes(self, rules):
        assert "negative_amount_only_refunds" not in failures(rules, total_amount=0.0)


class TestItems:
    def test_empty_items_on_delivered_fails(self, rules):
        assert "items_present_for_active_orders" in failures(
            rules, status="delivered", items=[])

    def test_empty_items_on_cancelled_passes(self, rules):
        assert "items_present_for_active_orders" not in failures(
            rules, status="cancelled", items=[])

    def test_missing_items_fails(self, rules):
        assert "items_present_for_active_orders" in failures(rules, items=None)


class TestSeverity:
    def test_severities_resolve(self, rules):
        assert rules.severity_of("order_id_not_null") == "critical"
        assert rules.severity_of("currency_iso_valid") == "warning"

    def test_uncastable_pseudo_rule_is_critical(self, rules):
        assert rules.severity_of("uncastable_total_amount") == "critical"
