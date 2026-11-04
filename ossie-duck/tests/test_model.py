from __future__ import annotations

import pytest

from ossie_duck import ModelValidationError, load_model, parse_model


def messages(exc: ModelValidationError) -> str:
    return "\n".join(str(i) for i in exc.value.issues)


def test_example_loads_without_issues(model):
    assert model.issues == []
    assert list(model.datasets) == ["store_sales", "date_dim", "customer", "item", "store"]
    refs = [m.ref for m in model.all_metrics()]
    assert "total_sales" in refs and "store_sales.total_quantity" in refs
    assert len(model.relationships) == 4


def test_is_time_follows_the_spec_defaults(model):
    date_dim = model.datasets["date_dim"].fields
    assert date_dim["d_date"].is_time  # Date datatype, empty `dimension: {}` -> defaults to true
    assert date_dim["d_year"].is_time  # explicit true on an Integer
    assert date_dim["d_quarter_name"].is_time  # explicit true, no datatype
    assert not date_dim["d_date_sk"].is_time  # explicit false
    assert not model.datasets["store_sales"].fields["ss_quantity"].is_time


def test_ai_context_synonyms_are_kept(model):
    assert "CLV" in model.metrics["customer_lifetime_value"].synonyms
    assert "POS data" in model.datasets["store_sales"].synonyms


def test_top_level_sql_beats_dialect_entries(doc):
    doc["datasets"][0]["fields"][2]["expression"] = {
        "sql": "amount * 2",
        "dialects": [{"dialect": "ANSI_SQL", "expression": "amount"}],
    }
    model = parse_model(doc)
    assert model.datasets["orders"].fields["amount"].expression == "amount * 2"


def test_dialect_preference_and_unusable_dialect_warning(doc):
    doc["datasets"][0]["fields"][2]["expression"] = {
        "dialects": [
            {"dialect": "ANSI_SQL", "expression": "amount"},
            {"dialect": "DUCKDB", "expression": "amount + 1"},
        ]
    }
    doc["datasets"][1]["fields"][1]["expression"] = {
        "dialects": [{"dialect": "SNOWFLAKE", "expression": "region::VARCHAR"}]
    }
    model = parse_model(doc)
    assert model.datasets["orders"].fields["amount"].expression == "amount + 1"
    assert model.datasets["customers"].fields["region"].expression is None
    assert any(i.level == "warning" and "region" in i.where for i in model.issues)


def test_wrong_version_is_rejected(doc):
    doc["version"] = "0.1.1"
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    assert "0.1.1" in messages(exc) and "0.2.0.dev0" in messages(exc)


def test_legacy_semantic_model_shape_gets_a_migration_hint():
    with pytest.raises(ModelValidationError) as exc:
        parse_model({"version": "0.1.1", "semantic_model": [{"name": "x", "datasets": []}]})
    assert "semantic_model" in messages(exc) and "Migrating" in messages(exc)


def test_schema_errors_carry_a_path(doc):
    del doc["datasets"][1]["source"]
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    assert "datasets[1]" in messages(exc) and "source" in messages(exc)


def test_not_yaml_and_not_a_mapping():
    with pytest.raises(ModelValidationError):
        parse_model("key: [unclosed")
    with pytest.raises(ModelValidationError):
        parse_model("- just\n- a list")


def test_json_documents_are_accepted(doc):
    import json

    assert parse_model(json.dumps(doc)).name == "t"


def test_dataset_metric_may_not_reach_into_another_dataset(doc):
    doc["datasets"][0]["metrics"].append({"name": "bad", "expression": {"sql": "SUM(amount) / COUNT(customers.id)"}})
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    assert "model-root" in messages(exc)


def test_dataset_metric_must_use_declared_fields(doc):
    doc["datasets"][0]["metrics"][0]["expression"] = {"sql": "SUM(not_a_field)"}
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    assert "not_a_field" in messages(exc)


def test_model_metric_must_be_qualified_and_resolvable(doc):
    doc["metrics"] = [
        {"name": "a", "expression": {"sql": "SUM(amount)"}},
        {"name": "b", "expression": {"sql": "SUM(nope.amount)"}},
        {"name": "c", "expression": {"sql": "SUM(orders.nope)"}},
    ]
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    text = messages(exc)
    assert "qualified" in text and "unknown dataset 'nope'" in text and "'nope' is not a declared field" in text


def test_relationships_are_checked(doc):
    doc["relationships"] = [
        {"name": "r1", "from": "orders", "to": "ghost", "from_columns": ["cust"], "to_columns": ["id"]},
        {"name": "r2", "from": "orders", "to": "customers", "from_columns": ["zzz"], "to_columns": ["id"]},
        {"name": "r3", "from": "orders", "to": "customers", "from_columns": ["cust", "id"], "to_columns": ["id"]},
    ]
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    text = messages(exc)
    assert "'ghost' does not exist" in text and "'zzz'" in text and "same length" in text


def test_names_share_a_namespace_inside_a_dataset(doc):
    doc["datasets"][0]["metrics"].append({"name": "amount", "expression": {"sql": "SUM(amount)"}})
    doc["datasets"].append(dict(doc["datasets"][1]))  # duplicate dataset name
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    text = messages(exc)
    assert "collides" in text and "duplicate dataset" in text


def test_key_columns_must_be_declared_fields(doc):
    doc["datasets"][0]["primary_key"] = ["missing"]
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    assert "missing" in messages(exc)


def test_unparseable_expression_is_an_error(doc):
    doc["datasets"][0]["fields"][2]["expression"] = {"sql": "amount +* ("}
    with pytest.raises(ModelValidationError) as exc:
        parse_model(doc)
    assert "cannot parse" in messages(exc)


def test_non_strict_keeps_errors_as_issues(doc):
    doc["datasets"][0]["primary_key"] = ["missing"]
    model = parse_model(doc, strict=False)
    assert any(i.level == "error" for i in model.issues)


def test_missing_aggregate_is_only_a_warning(doc):
    doc["metrics"] = [{"name": "flat", "expression": {"sql": "orders.amount"}}]
    model = parse_model(doc)
    assert any("no aggregate" in i.message for i in model.issues)


def test_load_model_reads_files(tmp_path, doc):
    import yaml

    path = tmp_path / "m.yaml"
    path.write_text(yaml.safe_dump(doc))
    assert load_model(path).name == "t"
