"""The ontology graph: structure, the three output formats, safety of text from the model, and the CLI."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from ossie_duck import parse_model
from ossie_duck.cli import main
from ossie_duck.graph import (
    DATASET, FIELD, METRIC, SYNONYM,
    RELATIONSHIP, HAS_FIELD, USES_DATASET, USES_FIELD, SCOPED_TO, SYNONYM_OF,
    build_graph, to_html, to_json, to_mermaid,
)

COFFEE = Path(__file__).resolve().parents[1] / "examples" / "coffee_shop" / "coffee_shop_model.yaml"


@pytest.fixture
def coffee():
    return parse_model(COFFEE.read_text())


def kinds(graph, attr="nodes"):
    return sorted({x.kind for x in getattr(graph, attr)})


def edges_of(graph, kind):
    return {(e.source, e.target, e.label) for e in graph.edges if e.kind == kind}


# ------------------------------------------------------------------ structure


def test_nodes_cover_the_whole_model(coffee):
    g = build_graph(coffee)
    by_kind = {k: [n.label for n in g.nodes if n.kind == k] for k in (DATASET, FIELD, METRIC, SYNONYM)}
    assert by_kind[DATASET] == ["orders", "customers"]
    assert len(by_kind[FIELD]) == 9  # 6 + 3
    assert by_kind[METRIC] == ["revenue", "average_order_value", "active_customers", "orders.order_count"]
    assert sorted(by_kind[SYNONYM]) == sorted(
        ["item", "what they bought", "market", "region", "location", "sales", "income", "turnover",
         "AOV", "basket size", "average basket"]
    )


def test_relationship_points_from_the_many_side_to_the_one_side(coffee):
    g = build_graph(coffee)
    assert edges_of(g, RELATIONSHIP) == {("dataset:orders", "dataset:customers", "customer_id = customer_id")}


def test_metrics_link_to_the_fields_and_datasets_they_read(coffee):
    g = build_graph(coffee)
    uses = edges_of(g, USES_FIELD)
    assert ("metric:revenue", "field:orders.line_total", "") in uses
    assert {t for s, t, _ in uses if s == "metric:average_order_value"} == {
        "field:orders.line_total", "field:orders.order_id"
    }
    assert ("metric:active_customers", "field:customers.customer_id", "") in uses
    ds = edges_of(g, USES_DATASET)
    assert ("metric:revenue", "dataset:orders", "") in ds
    assert ("metric:active_customers", "dataset:customers", "") in ds


def test_a_dataset_scoped_metric_belongs_to_its_dataset(coffee):
    g = build_graph(coffee)
    assert edges_of(g, SCOPED_TO) == {("metric:orders.order_count", "dataset:orders", "")}
    # it reads its own dataset, so there is no separate "uses dataset" arrow for it
    assert not any(e.source == "metric:orders.order_count" for e in g.edges if e.kind == USES_DATASET)


def test_synonyms_point_at_the_thing_they_rename(coffee):
    g = build_graph(coffee)
    syn = edges_of(g, SYNONYM_OF)
    assert ("synonym:metric:revenue:sales", "metric:revenue", "") in syn
    assert ("synonym:field:customers.country:region", "field:customers.country", "") in syn


def test_every_edge_ends_at_a_real_node(coffee, example_path):
    for text in (COFFEE.read_text(), example_path.read_text()):
        g = build_graph(parse_model(text))
        ids = {n.id for n in g.nodes}
        assert all(e.source in ids and e.target in ids for e in g.edges)
        assert len(ids) == len(g.nodes)  # ids are unique


def test_the_bundled_tpcds_model_graphs_without_error(model):
    g = build_graph(model)
    assert sum(n.kind == DATASET for n in g.nodes) == 5
    assert len(edges_of(g, RELATIONSHIP)) == 4


# ----------------------------------------------------------------------- views


def test_overview_hides_fields_and_shows_metric_to_dataset_links(coffee):
    v = build_graph(coffee).view()
    assert FIELD not in kinds(v)
    assert {HAS_FIELD, USES_FIELD}.isdisjoint(kinds(v, "edges"))
    assert USES_DATASET in kinds(v, "edges")


def test_full_view_shows_fields_and_field_level_links(coffee):
    v = build_graph(coffee).view(fields=True)
    assert FIELD in kinds(v) and USES_FIELD in kinds(v, "edges")
    assert USES_DATASET not in kinds(v, "edges")


def test_without_synonyms_no_synonym_node_or_edge_remains(coffee):
    v = build_graph(coffee).view(fields=True, synonyms=False)
    assert SYNONYM not in kinds(v) and SYNONYM_OF not in kinds(v, "edges")


def test_overview_drops_synonyms_of_fields_but_keeps_those_of_metrics(coffee):
    v = build_graph(coffee).view()
    labels = {n.label for n in v.nodes if n.kind == SYNONYM}
    assert "sales" in labels and "AOV" in labels
    assert "region" not in labels and "item" not in labels  # these name fields, which are hidden


# --------------------------------------------------------------------- mermaid


def test_mermaid_overview(coffee):
    text = to_mermaid(build_graph(coffee))
    assert text.startswith("flowchart LR\n")
    assert 'many to one: customer_id = customer_id' in text
    assert '[("orders  (key: order_id)")]' in text
    assert "also called" in text and "classDef dataset" in text
    assert "subgraph" not in text


def test_mermaid_full_nests_fields_inside_their_dataset(coffee):
    text = to_mermaid(build_graph(coffee), fields=True)
    assert text.count("subgraph") == 2 and text.count("\n  end\n") == 2
    assert '("order_month (time)")' in text  # time fields are marked


def test_mermaid_without_synonyms(coffee):
    assert "also called" not in to_mermaid(build_graph(coffee), synonyms=False)


def test_mermaid_labels_cannot_break_out_of_their_quotes(doc):
    doc["datasets"][0]["description"] = '<b>"hi"</b>'
    doc["metrics"][0]["ai_context"] = {"synonyms": ['x"]\n  click n0 call evil()\n  n9["y', "<img src=x>"]}
    doc["datasets"][0]["name"] = "orders"
    for fields in (False, True):
        text = to_mermaid(build_graph(parse_model(doc)), fields=fields)
        allowed = re.compile(r"^(flowchart LR|\s{2,4}(n\d+|class|classDef|style|subgraph|end)\b.*)$")
        stray = [ln for ln in text.splitlines() if not allowed.match(ln)]
        assert stray == [], stray  # the newline in the hostile synonym did not start a new statement
        assert "<img" not in text and "#lt;img" in text  # angle brackets are escaped
        assert not re.search(r"^\s*click\b", text, re.M)


def test_mermaid_long_labels_are_shortened(doc):
    doc["metrics"][0]["ai_context"] = {"synonyms": ["w" * 300]}
    text = to_mermaid(build_graph(parse_model(doc)))
    assert "w" * 100 not in text and "…" in text


@pytest.mark.skipif(shutil.which("mmdc") is None, reason="Mermaid CLI (mmdc) not installed")
@pytest.mark.parametrize("fields", [False, True])
def test_mermaid_output_is_accepted_by_the_mermaid_parser(coffee, tmp_path, fields):
    src, out = tmp_path / "g.mmd", tmp_path / "g.svg"
    src.write_text(to_mermaid(build_graph(coffee), fields=fields))
    cfg = tmp_path / "pp.json"
    cfg.write_text('{"args": ["--no-sandbox"]}')
    r = subprocess.run(["mmdc", "-p", str(cfg), "-i", str(src), "-o", str(out)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert out.stat().st_size > 1000


# ------------------------------------------------------------------------ html


def _embedded(html: str) -> dict:
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "graph data block not found"
    return json.loads(m.group(1))


def test_html_is_self_contained_and_carries_the_whole_graph(coffee):
    html = to_html(build_graph(coffee))
    assert html.startswith("<!doctype html>")
    assert not re.search(r'(src|href)="https?://', html)  # nothing is loaded from the internet
    data = _embedded(html)
    assert data["model"] == "coffee_shop" and len(data["nodes"]) == 9 + 2 + 4 + 11
    assert {e["kind"] for e in data["edges"]} >= {"relationship", "has_field", "uses_field", "synonym_of"}


def test_html_cannot_be_broken_by_text_in_the_model(doc):
    doc["description"] = '</script><img src=x onerror="alert(1)">'
    doc["metrics"][0]["description"] = "<script>alert(2)</script> "
    html = to_html(build_graph(parse_model(doc)), title="</title><script>alert(3)</script>")
    assert "<script>alert" not in html and "</title><script" not in html
    assert html.count("</script>") == html.count("<script")  # only the page's own script tags
    assert "<img" not in html
    data = _embedded(html)  # and the text survives intact as data
    assert data["description"].startswith("</script>")
    assert "&lt;/title&gt;" in html


def test_html_page_uses_textcontent_not_innerhtml():
    html = to_html(build_graph(parse_model(COFFEE.read_text())))
    assert "innerHTML" not in html and "insertAdjacentHTML" not in html and "document.write" not in html


# ------------------------------------------------------------------------ json


def test_json_round_trips(coffee):
    g = build_graph(coffee)
    data = json.loads(to_json(g))
    assert data == g.to_dict()
    assert data["spec_version"] == "0.2.0.dev0"


# ------------------------------------------------------------------------- CLI


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_prints_mermaid_by_default(capsys):
    code, out, _ = run(capsys, "graph", COFFEE)
    assert code == 0 and out.startswith("flowchart LR")


def test_cli_fields_flag(capsys):
    code, out, _ = run(capsys, "graph", COFFEE, "--fields")
    assert code == 0 and "subgraph" in out


def test_cli_no_synonyms_flag(capsys):
    code, out, _ = run(capsys, "graph", COFFEE, "--no-synonyms")
    assert code == 0 and "also called" not in out


def test_cli_format_follows_the_output_extension(capsys, tmp_path):
    for name, check in {
        "g.html": lambda t: t.startswith("<!doctype html>"),
        "g.json": lambda t: json.loads(t)["model"] == "coffee_shop",
        "g.mmd": lambda t: t.startswith("flowchart LR"),
        "g.md": lambda t: t.startswith("```mermaid\nflowchart LR") and t.rstrip().endswith("```"),
    }.items():
        path = tmp_path / name
        code, out, err = run(capsys, "graph", COFFEE, "-o", path)
        assert code == 0 and out == "" and "wrote" in err, name
        assert check(path.read_text()), name


def test_cli_explicit_format_beats_the_extension(capsys, tmp_path):
    path = tmp_path / "g.txt"
    code, *_ = run(capsys, "graph", COFFEE, "--format", "json", "-o", path)
    assert code == 0 and json.loads(path.read_text())["model"] == "coffee_shop"


def test_cli_html_title(capsys):
    code, out, _ = run(capsys, "graph", COFFEE, "--format", "html", "--title", "My map")
    assert code == 0 and "<title>My map</title>" in out


def test_cli_reports_an_invalid_model_cleanly(capsys, tmp_path, doc):
    doc["version"] = "9.9"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(doc))
    code, out, err = run(capsys, "graph", bad)
    assert code == 1 and out == "" and "9.9" in err


def test_cli_reports_a_missing_file_cleanly(capsys, tmp_path):
    code, out, err = run(capsys, "graph", tmp_path / "nope.yaml")
    assert code == 1 and out == "" and "error:" in err


# ------------------------------------------------- the documentation matches the tool

README = Path(__file__).resolve().parents[1] / "README.md"
DOCS = README.parent / "docs"


def _readme_mermaid_blocks() -> list[str]:
    return re.findall(r"^```mermaid\n(flowchart LR\n  (?:n0|subgraph n0).*?)^```", README.read_text(), re.S | re.M)


def test_readme_graphs_are_exactly_what_the_tool_prints(coffee):
    blocks = _readme_mermaid_blocks()
    assert to_mermaid(build_graph(coffee)) in blocks, "README overview diagram is stale: re-run `ossie-duck graph`"
    assert to_mermaid(build_graph(coffee), fields=True) in blocks, "README --fields diagram is stale"


@pytest.mark.parametrize(
    "html_name, model_path",
    [
        ("coffee_shop_graph.html", COFFEE),
        ("tpcds_graph.html", COFFEE.parents[1] / "tpcds_semantic_model.yaml"),
    ],
)
def test_sample_html_pages_match_the_current_generator(html_name, model_path):
    expected = to_html(build_graph(parse_model(model_path.read_text())))
    assert (DOCS / html_name).read_text(encoding="utf-8") == expected, f"docs/{html_name} is stale: regenerate it"


def test_every_image_the_readme_links_exists():
    for rel in re.findall(r"!\[[^\]]*\]\((docs/[^)]+)\)", README.read_text()):
        assert (README.parent / rel).is_file(), rel
