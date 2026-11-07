"""Draw an Apache Ossie semantic model as a graph (an "ontology map").

A model is already a graph: datasets are linked by relationships, metrics are built from
fields, and ``ai_context`` synonyms are alternative names for things. This module turns a
:class:`~ossie_duck.model.SemanticModel` into nodes and edges, and renders them as

* **Mermaid** text (GitHub renders it in a README),
* a single **self-contained HTML** file with an interactive graph (no internet needed), or
* **JSON** (nodes and edges), for other tools.

Two levels of detail:

* *overview* (default): datasets, relationships, metrics and synonyms;
* *full* (``fields=True``): also every field, and which fields each metric uses.

Nothing here talks to a database; it only reads the model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlglot import exp
from sqlglot.errors import SqlglotError

from .model import SemanticModel, parse_sql

# node kinds
DATASET, FIELD, METRIC, SYNONYM = "dataset", "field", "metric", "synonym"
# edge kinds
RELATIONSHIP, HAS_FIELD, USES_FIELD, USES_DATASET, SCOPED_TO, SYNONYM_OF = (
    "relationship",
    "has_field",
    "uses_field",
    "uses_dataset",
    "scoped_to",
    "synonym_of",
)


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str
    label: str = ""


@dataclass
class Graph:
    model_name: str
    description: str
    spec_version: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "description": self.description,
            "spec_version": self.spec_version,
            "nodes": [{"id": n.id, "kind": n.kind, "label": n.label, "details": n.details} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target, "kind": e.kind, "label": e.label} for e in self.edges],
        }

    def view(self, *, fields: bool = False, synonyms: bool = True) -> "Graph":
        """The subgraph to draw: overview (``fields=False``) or full, with or without synonyms."""
        hidden_edges = {USES_DATASET} if fields else {HAS_FIELD, USES_FIELD}
        keep = {n.id for n in self.nodes if (fields or n.kind != FIELD) and (synonyms or n.kind != SYNONYM)}
        # a synonym whose target is hidden would dangle, so it is dropped below
        edges = [
            e for e in self.edges
            if e.kind not in hidden_edges and e.source in keep and e.target in keep
        ]
        linked_synonyms = {e.source for e in edges if e.kind == SYNONYM_OF}
        nodes = [n for n in self.nodes if n.id in keep and (n.kind != SYNONYM or n.id in linked_synonyms)]
        return Graph(self.model_name, self.description, self.spec_version, nodes, edges)


# --------------------------------------------------------------------------- #
# Model -> graph
# --------------------------------------------------------------------------- #


def _field_refs(model: SemanticModel, expression: str | None, scope: str | None) -> list[tuple[str, str]]:
    """The ``(dataset, field)`` pairs an expression reads, in order, without duplicates."""
    if not expression:
        return []
    try:
        tree = parse_sql(expression)
    except SqlglotError:
        return []
    refs: list[tuple[str, str]] = []
    for col in tree.find_all(exp.Column):
        dataset = col.table or scope
        if dataset in model.datasets and col.name in model.datasets[dataset].fields:
            pair = (dataset, col.name)
            if pair not in refs:
                refs.append(pair)
    return refs


def build_graph(model: SemanticModel) -> Graph:
    """Turn a model into nodes and edges (the full graph; use :meth:`Graph.view` to trim it)."""
    g = Graph(model.name, model.description, model.version)
    node_ids: set[str] = set()

    def add(node: Node) -> None:
        if node.id not in node_ids:
            node_ids.add(node.id)
            g.nodes.append(node)

    def add_synonyms(target: str, words: tuple[str, ...]) -> None:
        for word in words:
            sid = f"synonym:{target}:{word}"
            add(Node(sid, SYNONYM, word, {"names": target}))
            g.edges.append(Edge(sid, target, SYNONYM_OF))

    for ds in model.datasets.values():
        add(
            Node(
                f"dataset:{ds.name}",
                DATASET,
                ds.name,
                {
                    "description": ds.description,
                    "source": ds.source,
                    "primary_key": list(ds.primary_key),
                    "fields": len(ds.fields),
                },
            )
        )
        add_synonyms(f"dataset:{ds.name}", ds.synonyms)
        for f in ds.fields.values():
            add(
                Node(
                    f"field:{ds.name}.{f.name}",
                    FIELD,
                    f.name,
                    {
                        "dataset": ds.name,
                        "description": f.description,
                        "datatype": f.datatype or "",
                        "is_time": f.is_time,
                        "expression": f.expression or "",
                    },
                )
            )
            g.edges.append(Edge(f"dataset:{ds.name}", f"field:{ds.name}.{f.name}", HAS_FIELD))
            add_synonyms(f"field:{ds.name}.{f.name}", f.synonyms)

    for r in model.relationships:
        on = ", ".join(f"{a} = {b}" for a, b in zip(r.from_columns, r.to_columns))
        g.edges.append(Edge(f"dataset:{r.from_dataset}", f"dataset:{r.to_dataset}", RELATIONSHIP, on))

    for m in model.all_metrics():
        mid = f"metric:{m.ref}"
        add(
            Node(
                mid,
                METRIC,
                m.ref,
                {
                    "description": m.description,
                    "datatype": m.datatype or "",
                    "expression": m.expression or "",
                    "scope": f"dataset {m.dataset}" if m.dataset else "whole model",
                },
            )
        )
        add_synonyms(mid, m.synonyms)
        refs = _field_refs(model, m.expression, m.dataset)
        if m.dataset:
            g.edges.append(Edge(mid, f"dataset:{m.dataset}", SCOPED_TO))
        for dataset in dict.fromkeys(d for d, _ in refs):
            if dataset != m.dataset:
                g.edges.append(Edge(mid, f"dataset:{dataset}", USES_DATASET))
        for dataset, fname in refs:
            g.edges.append(Edge(mid, f"field:{dataset}.{fname}", USES_FIELD))
    return g


# --------------------------------------------------------------------------- #
# Mermaid
# --------------------------------------------------------------------------- #

_CLASSDEFS = (
    "  classDef dataset fill:#e6f6ec,stroke:#2f855a,color:#12361f",
    "  classDef metric fill:#fff3d6,stroke:#b7791f,color:#3b2a06",
    "  classDef field fill:#eef2f7,stroke:#64748b,color:#1e293b",
    "  classDef synonym fill:#f3e8ff,stroke:#805ad5,color:#3b1f66",
)


def _q(text: str, limit: int = 70) -> str:
    """Make text safe inside a double-quoted Mermaid label."""
    flat = " ".join(str(text).split())
    if len(flat) > limit:
        flat = flat[: limit - 1] + "…"
    return flat.replace("&", "#amp;").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def to_mermaid(graph: Graph, *, fields: bool = False, synonyms: bool = True) -> str:
    """Render a Mermaid ``flowchart``. Paste it into a README or any Mermaid viewer."""
    view = graph.view(fields=fields, synonyms=synonyms)
    ids = {n.id: f"n{i}" for i, n in enumerate(view.nodes)}
    lines = ["flowchart LR"]

    def dataset_label(n: Node) -> str:
        key = n.details.get("primary_key") or []
        return n.label + (f"  (key: {_q(', '.join(key))})" if key else "")

    members: dict[str, list[Node]] = {}  # dataset node id -> the fields drawn inside its box
    if fields:
        for n in view.nodes:
            if n.kind == FIELD:
                members.setdefault(f"dataset:{n.details['dataset']}", []).append(n)

    for n in view.nodes:
        if n.kind == DATASET:
            if fields:
                lines.append(f'  subgraph {ids[n.id]}["{dataset_label(n)}"]')
                for f in members.get(n.id, []):
                    mark = " (time)" if f.details.get("is_time") else ""
                    lines.append(f'    {ids[f.id]}("{_q(f.label)}{mark}")')
                lines.append("  end")
            else:
                lines.append(f'  {ids[n.id]}[("{dataset_label(n)}")]')
        elif n.kind == METRIC:
            lines.append(f'  {ids[n.id]}{{{{"{_q(n.label)}"}}}}')
        elif n.kind == SYNONYM:
            lines.append(f'  {ids[n.id]}(["{_q(n.label)}"])')

    for e in view.edges:
        a, b = ids[e.source], ids[e.target]
        if e.kind == RELATIONSHIP:
            lines.append(f'  {a} -->|"many to one: {_q(e.label)}"| {b}')
        elif e.kind in (USES_DATASET, USES_FIELD):
            lines.append(f"  {a} -.->|uses| {b}")
        elif e.kind == SCOPED_TO:
            lines.append(f"  {a} -.->|belongs to| {b}")
        elif e.kind == SYNONYM_OF:
            lines.append(f"  {a} ---|also called| {b}")
        # HAS_FIELD is shown by nesting, not by an edge

    lines.extend(_CLASSDEFS)
    for kind in (DATASET, METRIC, FIELD, SYNONYM):
        if kind == DATASET and fields:
            continue  # datasets are drawn as boxes around their fields; styled below
        names = [ids[n.id] for n in view.nodes if n.kind == kind]
        if names:
            lines.append(f"  class {','.join(names)} {kind}")
    if fields:
        for n in view.nodes:
            if n.kind == DATASET:
                lines.append(f"  style {ids[n.id]} fill:#f2faf5,stroke:#2f855a,color:#12361f")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Interactive HTML
# --------------------------------------------------------------------------- #


def to_json(graph: Graph) -> str:
    return json.dumps(graph.to_dict(), indent=2, ensure_ascii=False) + "\n"


def to_html(graph: Graph, *, title: str | None = None) -> str:
    """One self-contained HTML page: drag nodes, zoom, search, click for details.

    The full graph is embedded as data; the page itself decides what to show. It loads
    nothing from the internet, so it works offline and can be emailed or attached.
    """
    page_title = title or f"{graph.model_name}: ontology graph"
    # Text from the model is data only: it is JSON-encoded here and written to the page with
    # textContent, never as HTML. "<" is escaped so a "</script>" inside the model cannot end the block.
    data = json.dumps(graph.to_dict(), ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    safe_title = page_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _HTML.replace("__TITLE__", safe_title).replace("__DATA__", data)


_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    --bg: #ffffff; --panel: #f6f8fa; --text: #1f2933; --muted: #5f6b7a; --line: #c5ccd6; --accent: #2b6cb0;
    --dataset-fill: #e6f6ec; --dataset-stroke: #2f855a; --dataset-text: #12361f;
    --metric-fill: #fff3d6; --metric-stroke: #b7791f; --metric-text: #3b2a06;
    --field-fill: #eef2f7; --field-stroke: #64748b; --field-text: #1e293b;
    --synonym-fill: #f3e8ff; --synonym-stroke: #805ad5; --synonym-text: #3b1f66;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #11151a; --panel: #1a2028; --text: #e6e9ee; --muted: #9aa5b4; --line: #3a4552; --accent: #63b3ed;
      --dataset-fill: #173326; --dataset-stroke: #48bb78; --dataset-text: #d3f2df;
      --metric-fill: #3a2d0f; --metric-stroke: #ecc94b; --metric-text: #fbefc7;
      --field-fill: #232b36; --field-stroke: #8392a5; --field-text: #dbe3ee;
      --synonym-fill: #2c2140; --synonym-stroke: #b794f4; --synonym-text: #eadcff;
    }
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         display: flex; flex-direction: column; }
  header { padding: 12px 16px; border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
  header h1 { font-size: 16px; margin: 0; }
  header .sub { color: var(--muted); font-size: 13px; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; margin-left: auto; }
  .controls label { display: inline-flex; gap: 6px; align-items: center; cursor: pointer; }
  input[type=search] { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; width: 170px; }
  button { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: 5px 10px; cursor: pointer; }
  button:hover { border-color: var(--accent); }
  main { flex: 1; min-height: 0; display: flex; }
  #stage { flex: 1; min-width: 0; position: relative; }
  svg { width: 100%; height: 100%; display: block; cursor: grab; touch-action: none; }
  svg.panning { cursor: grabbing; }
  aside { width: 300px; max-width: 40%; border-left: 1px solid var(--line); background: var(--panel); padding: 14px; overflow: auto; }
  aside h2 { font-size: 15px; margin: 0 0 4px; word-break: break-word; }
  aside .kind { color: var(--muted); text-transform: uppercase; letter-spacing: .04em; font-size: 11px; margin-bottom: 8px; }
  aside dl { margin: 0; }
  aside dt { color: var(--muted); font-size: 12px; margin-top: 10px; }
  aside dd { margin: 2px 0 0; word-break: break-word; }
  aside code { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--bg); border: 1px solid var(--line); border-radius: 4px; padding: 1px 4px; display: inline-block; max-width: 100%; white-space: pre-wrap; }
  .legend { position: absolute; left: 12px; bottom: 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font-size: 12px; display: grid; gap: 4px; }
  .legend i { display: inline-block; width: 14px; height: 14px; border-radius: 3px; border: 2px solid; vertical-align: -2px; margin-right: 6px; }
  .hint { position: absolute; right: 12px; bottom: 12px; color: var(--muted); font-size: 12px; background: var(--bg); padding: 2px 6px; border-radius: 6px; }
  .node { cursor: pointer; outline: none; }
  .node rect, .node polygon, .node ellipse { stroke-width: 2; }
  .node text { font-size: 12px; text-anchor: middle; dominant-baseline: central; pointer-events: none; }
  .node.dataset rect { fill: var(--dataset-fill); stroke: var(--dataset-stroke); } .node.dataset text { fill: var(--dataset-text); font-weight: 600; }
  .node.metric polygon { fill: var(--metric-fill); stroke: var(--metric-stroke); } .node.metric text { fill: var(--metric-text); }
  .node.field rect { fill: var(--field-fill); stroke: var(--field-stroke); } .node.field text { fill: var(--field-text); }
  .node.synonym ellipse { fill: var(--synonym-fill); stroke: var(--synonym-stroke); stroke-dasharray: 4 3; } .node.synonym text { fill: var(--synonym-text); }
  .node:focus rect, .node:focus polygon, .node:focus ellipse { stroke: var(--accent); stroke-width: 3.5; }
  .node.selected rect, .node.selected polygon, .node.selected ellipse { stroke: var(--accent); stroke-width: 3.5; }
  .dim { opacity: .13; }
  .edge { fill: none; stroke: var(--line); stroke-width: 1.5; }
  .edge.relationship { stroke: var(--dataset-stroke); stroke-width: 2.5; }
  .edge.uses_dataset, .edge.uses_field, .edge.scoped_to { stroke: var(--metric-stroke); stroke-dasharray: 5 4; }
  .edge.synonym_of { stroke: var(--synonym-stroke); stroke-dasharray: 2 3; }
  .edge.has_field { stroke: var(--field-stroke); }
  .elabel { font-size: 11px; fill: var(--muted); text-anchor: middle; paint-order: stroke; stroke: var(--bg); stroke-width: 4px; pointer-events: none; }
  marker path { fill: var(--line); }
  @media (max-width: 700px) { main { flex-direction: column; } aside { width: 100%; max-width: none; max-height: 38%; border-left: 0; border-top: 1px solid var(--line); } }
</style>
</head>
<body>
<header>
  <div><h1 id="title"></h1><div class="sub" id="subtitle"></div></div>
  <div class="controls">
    <input id="search" type="search" placeholder="Find a name…" aria-label="Find a node by name">
    <label><input type="checkbox" id="showFields"> Fields</label>
    <label><input type="checkbox" id="showSyn" checked> Synonyms</label>
    <button id="reset" type="button">Reset view</button>
  </div>
</header>
<main>
  <div id="stage">
    <svg id="svg" role="img" aria-label="Graph of the semantic model: datasets, relationships, metrics and synonyms">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker>
      </defs>
      <g id="world"><g id="edges"></g><g id="labels"></g><g id="nodes"></g></g>
    </svg>
    <div class="legend" aria-hidden="true">
      <span><i style="background:var(--dataset-fill);border-color:var(--dataset-stroke)"></i>Dataset (a table)</span>
      <span><i style="background:var(--metric-fill);border-color:var(--metric-stroke)"></i>Metric (a business number)</span>
      <span><i style="background:var(--field-fill);border-color:var(--field-stroke)"></i>Field (a column or computed value)</span>
      <span><i style="background:var(--synonym-fill);border-color:var(--synonym-stroke)"></i>Synonym (another name)</span>
    </div>
    <div class="hint">Drag to move · scroll to zoom · click a node for details</div>
  </div>
  <aside id="side" aria-live="polite"><h2>Details</h2><div class="kind">click a node</div><p>Click any node to see what it means. Arrows between datasets read "many to one": many orders belong to one customer.</p></aside>
</main>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("graph-data").textContent);
  var NS = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("svg"), world = document.getElementById("world");
  var gEdges = document.getElementById("edges"), gLabels = document.getElementById("labels"), gNodes = document.getElementById("nodes");
  document.getElementById("title").textContent = data.model + " · ontology graph";
  document.getElementById("subtitle").textContent = (data.description || "") + (data.description ? " · " : "") + "Apache Ossie spec " + data.spec_version;
  document.title = document.getElementById("title").textContent;

  function el(name, attrs, parent) { var e = document.createElementNS(NS, name); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }

  var nodes = data.nodes.map(function (n, i) {
    var w = Math.max(54, n.label.length * 7.2 + 24);
    if (n.kind === "metric") w += 22;
    var h = n.kind === "dataset" ? 40 : 30;
    var a = (i / Math.max(1, data.nodes.length)) * Math.PI * 2;
    return { id: n.id, kind: n.kind, label: n.label, details: n.details || {}, w: w, h: h, x: 400 * Math.cos(a), y: 300 * Math.sin(a), vx: 0, vy: 0, fixed: false, vis: true };
  });
  var byId = {}; nodes.forEach(function (n) { byId[n.id] = n; });
  var edges = data.edges.map(function (e) { return { s: byId[e.source], t: byId[e.target], kind: e.kind, label: e.label || "", vis: true }; })
    .filter(function (e) { return e.s && e.t; });

  var showFields = document.getElementById("showFields"), showSyn = document.getElementById("showSyn");
  function applyVisibility() {
    nodes.forEach(function (n) { n.vis = !((n.kind === "field" && !showFields.checked) || (n.kind === "synonym" && !showSyn.checked)); });
    edges.forEach(function (e) {
      var kindOk = showFields.checked ? e.kind !== "uses_dataset" : (e.kind !== "has_field" && e.kind !== "uses_field");
      e.vis = kindOk && e.s.vis && e.t.vis;
    });
    nodes.forEach(function (n) { if (n.kind === "synonym" && n.vis && !edges.some(function (e) { return e.vis && e.s === n; })) n.vis = false; });
    draw(); alpha = 1; tick();
  }

  // ----- drawing
  var nodeEls = new Map(), edgeEls = new Map(), labelEls = new Map();
  var selected = null, query = "";
  function nodeShape(n, g) {
    if (n.kind === "metric") {
      var hw = n.w / 2, hh = n.h / 2, pts = [[-hw, 0], [-hw + 12, -hh], [hw - 12, -hh], [hw, 0], [hw - 12, hh], [-hw + 12, hh]].map(function (p) { return p.join(","); }).join(" ");
      el("polygon", { points: pts }, g);
    } else if (n.kind === "synonym") {
      el("ellipse", { rx: n.w / 2, ry: n.h / 2 }, g);
    } else {
      el("rect", { x: -n.w / 2, y: -n.h / 2, width: n.w, height: n.h, rx: n.kind === "dataset" ? 10 : 6 }, g);
    }
    var t = el("text", {}, g); t.textContent = n.label;
  }
  function draw() {
    gEdges.textContent = ""; gLabels.textContent = ""; gNodes.textContent = "";
    nodeEls.clear(); edgeEls.clear(); labelEls.clear();
    edges.forEach(function (e) {
      if (!e.vis) return;
      var p = el("path", { "class": "edge " + e.kind }, gEdges);
      if (e.kind === "relationship" || e.kind === "uses_dataset" || e.kind === "uses_field" || e.kind === "scoped_to") p.setAttribute("marker-end", "url(#arrow)");
      edgeEls.set(e, p);
      var text = e.kind === "relationship" ? "many to one: " + e.label : e.kind === "synonym_of" ? "" : e.kind === "scoped_to" ? "belongs to" : e.kind === "uses_dataset" || e.kind === "uses_field" ? "uses" : "";
      if (text) { var l = el("text", { "class": "elabel" }, gLabels); l.textContent = text; labelEls.set(e, l); }
    });
    nodes.forEach(function (n) {
      if (!n.vis) return;
      var g = el("g", { "class": "node " + n.kind, tabindex: 0, role: "button", "aria-label": n.kind + " " + n.label }, gNodes);
      nodeShape(n, g); nodeEls.set(n, g); attach(n, g);
    });
    place(); highlight();
  }
  function edgeAnchor(a, b) {  // point on a's box edge towards b
    var dx = b.x - a.x, dy = b.y - a.y; if (!dx && !dy) return { x: a.x, y: a.y };
    var sx = (a.w / 2 + 3) / Math.abs(dx || 1e-9), sy = (a.h / 2 + 3) / Math.abs(dy || 1e-9), k = Math.min(sx, sy);
    return { x: a.x + dx * k, y: a.y + dy * k };
  }
  function place() {
    nodeEls.forEach(function (g, n) { g.setAttribute("transform", "translate(" + n.x.toFixed(1) + "," + n.y.toFixed(1) + ")"); });
    edgeEls.forEach(function (p, e) {
      var a = edgeAnchor(e.s, e.t), b = edgeAnchor(e.t, e.s);
      p.setAttribute("d", "M" + a.x.toFixed(1) + "," + a.y.toFixed(1) + " L" + b.x.toFixed(1) + "," + b.y.toFixed(1));
      var l = labelEls.get(e); if (l) { l.setAttribute("x", ((a.x + b.x) / 2).toFixed(1)); l.setAttribute("y", ((a.y + b.y) / 2 - 4).toFixed(1)); }
    });
  }
  function neighbours(n) { var s = new Set([n]); edges.forEach(function (e) { if (e.vis && (e.s === n || e.t === n)) { s.add(e.s); s.add(e.t); } }); return s; }
  function highlight() {
    var q = query.trim().toLowerCase(), hits = null;
    var focus = !q && selected && selected.vis ? neighbours(selected) : null;  // a search overrides the selection
    if (q) { hits = new Set(); nodes.forEach(function (n) { if (n.vis && n.label.toLowerCase().indexOf(q) >= 0) hits.add(n); }); }
    nodeEls.forEach(function (g, n) {
      var on = (!focus || focus.has(n)) && (!hits || hits.has(n));
      g.classList.toggle("dim", !on); g.classList.toggle("selected", n === selected);
    });
    edgeEls.forEach(function (p, e) {
      var on = (!focus || (focus.has(e.s) && focus.has(e.t))) && (!hits || hits.has(e.s) || hits.has(e.t));
      p.classList.toggle("dim", !on); var l = labelEls.get(e); if (l) l.classList.toggle("dim", !on);
    });
  }

  // ----- force layout (small and dependency-free)
  var alpha = 1, raf = 0;
  function step() {
    var vis = nodes.filter(function (n) { return n.vis; });
    var i, j, a, b, dx, dy, d2, d, f;
    for (i = 0; i < vis.length; i++) for (j = i + 1; j < vis.length; j++) {
      a = vis[i]; b = vis[j]; dx = b.x - a.x; dy = b.y - a.y; d2 = dx * dx + dy * dy + 0.01; d = Math.sqrt(d2);
      f = 26000 / d2 * alpha; a.vx -= dx / d * f; a.vy -= dy / d * f; b.vx += dx / d * f; b.vy += dy / d * f;
      var minX = (a.w + b.w) / 2 + 14, minY = (a.h + b.h) / 2 + 10;  // keep boxes apart
      if (Math.abs(dx) < minX && Math.abs(dy) < minY) { var push = 1.5 * alpha; if (Math.abs(dx) / minX > Math.abs(dy) / minY) { a.vx -= Math.sign(dx || 1) * push; b.vx += Math.sign(dx || 1) * push; } else { a.vy -= Math.sign(dy || 1) * push; b.vy += Math.sign(dy || 1) * push; } }
    }
    edges.forEach(function (e) {
      if (!e.vis) return;
      var want = e.kind === "relationship" ? 230 : e.kind === "synonym_of" ? 95 : e.kind === "has_field" ? 120 : 150;
      var s = e.s, t = e.t; dx = t.x - s.x; dy = t.y - s.y; d = Math.sqrt(dx * dx + dy * dy) || 1;
      f = (d - want) * 0.02 * alpha; s.vx += dx / d * f; s.vy += dy / d * f; t.vx -= dx / d * f; t.vy -= dy / d * f;
    });
    vis.forEach(function (n) {
      n.vx -= n.x * 0.004 * alpha; n.vy -= n.y * 0.004 * alpha;
      if (!n.fixed) { n.x += n.vx; n.y += n.vy; }
      n.vx *= 0.6; n.vy *= 0.6;
    });
    alpha *= 0.985;
  }
  function tick() {
    cancelAnimationFrame(raf);
    (function loop() { for (var k = 0; k < 3; k++) step(); place(); if (alpha > 0.02) raf = requestAnimationFrame(loop); else fit(); })();
  }

  // ----- pan / zoom
  var view = { x: 0, y: 0, k: 1 };
  function applyView() { world.setAttribute("transform", "translate(" + view.x + "," + view.y + ") scale(" + view.k + ")"); }
  function fit() {
    var vis = nodes.filter(function (n) { return n.vis; }); if (!vis.length) return;
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    vis.forEach(function (n) { x0 = Math.min(x0, n.x - n.w / 2); x1 = Math.max(x1, n.x + n.w / 2); y0 = Math.min(y0, n.y - n.h / 2); y1 = Math.max(y1, n.y + n.h / 2); });
    var W = svg.clientWidth || 800, H = svg.clientHeight || 600, pad = 50;
    view.k = Math.max(0.2, Math.min(1.6, Math.min((W - pad * 2) / (x1 - x0 || 1), (H - pad * 2) / (y1 - y0 || 1))));
    view.x = W / 2 - ((x0 + x1) / 2) * view.k; view.y = H / 2 - ((y0 + y1) / 2) * view.k; applyView();
  }
  function toWorld(ev) { var r = svg.getBoundingClientRect(); return { x: (ev.clientX - r.left - view.x) / view.k, y: (ev.clientY - r.top - view.y) / view.k }; }
  svg.addEventListener("wheel", function (ev) {
    ev.preventDefault(); var r = svg.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
    var k2 = Math.max(0.15, Math.min(3, view.k * (ev.deltaY < 0 ? 1.12 : 1 / 1.12)));
    view.x = mx - (mx - view.x) * (k2 / view.k); view.y = my - (my - view.y) * (k2 / view.k); view.k = k2; applyView();
  }, { passive: false });
  var pan = null;
  svg.addEventListener("pointerdown", function (ev) {
    if (ev.target.closest(".node")) return;
    pan = { x: ev.clientX - view.x, y: ev.clientY - view.y }; svg.classList.add("panning"); svg.setPointerCapture(ev.pointerId);
    selected = null; highlight(); showDetails(null);
  });
  svg.addEventListener("pointermove", function (ev) { if (pan) { view.x = ev.clientX - pan.x; view.y = ev.clientY - pan.y; applyView(); } });
  function endPan() { pan = null; svg.classList.remove("panning"); }
  svg.addEventListener("pointerup", endPan); svg.addEventListener("pointercancel", endPan);

  // ----- dragging nodes, selecting
  function attach(n, g) {
    var drag = null, moved = false;
    g.addEventListener("pointerdown", function (ev) {
      ev.stopPropagation(); var p = toWorld(ev); drag = { dx: n.x - p.x, dy: n.y - p.y }; moved = false; n.fixed = true; g.setPointerCapture(ev.pointerId);
    });
    g.addEventListener("pointermove", function (ev) {
      if (!drag) return; var p = toWorld(ev); n.x = p.x + drag.dx; n.y = p.y + drag.dy; moved = true; place();
      if (alpha < 0.3) { alpha = 0.3; tick(); }
    });
    g.addEventListener("pointerup", function () { if (!drag) return; drag = null; n.fixed = false; if (!moved) select(n); });
    g.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n); } });
  }
  function select(n) { selected = n; highlight(); showDetails(n); }

  // ----- details panel (everything goes in with textContent)
  var side = document.getElementById("side");
  var KIND = { dataset: "Dataset", field: "Field", metric: "Metric", synonym: "Synonym" };
  function row(dl, term, value, code) {
    if (value === "" || value === undefined || value === null || (Array.isArray(value) && !value.length)) return;
    var dt = document.createElement("dt"); dt.textContent = term; var dd = document.createElement("dd");
    var text = Array.isArray(value) ? value.join(", ") : String(value);
    if (code) { var c = document.createElement("code"); c.textContent = text; dd.appendChild(c); } else dd.textContent = text;
    dl.appendChild(dt); dl.appendChild(dd);
  }
  function relatedNames(n, filter) {
    var out = []; edges.forEach(function (e) { var o = filter(e, n); if (o && out.indexOf(o.label) < 0) out.push(o.label); }); return out;
  }
  function showDetails(n) {
    side.textContent = "";
    var h = document.createElement("h2"), k = document.createElement("div"); k.className = "kind";
    if (!n) { h.textContent = "Details"; k.textContent = "click a node"; side.appendChild(h); side.appendChild(k); return; }
    h.textContent = n.label; k.textContent = KIND[n.kind]; side.appendChild(h); side.appendChild(k);
    var d = n.details, dl = document.createElement("dl");
    if (n.kind === "dataset") {
      row(dl, "What it is", d.description); row(dl, "Table", d.source, true); row(dl, "Key", d.primary_key); row(dl, "Fields", d.fields);
      row(dl, "Joins to (many to one)", relatedNames(n, function (e, x) { return e.kind === "relationship" && e.s === x ? e.t : null; }));
      row(dl, "Joined from", relatedNames(n, function (e, x) { return e.kind === "relationship" && e.t === x ? e.s : null; }));
      row(dl, "Metrics using it", relatedNames(n, function (e, x) { return (e.kind === "uses_dataset" || e.kind === "scoped_to") && e.t === x ? e.s : null; }));
    } else if (n.kind === "metric") {
      row(dl, "What it means", d.description); row(dl, "Formula", d.expression, true); row(dl, "Type", d.datatype); row(dl, "Defined for", d.scope);
      row(dl, "Reads fields", relatedNames(n, function (e, x) { return e.kind === "uses_field" && e.s === x ? e.t : null; }));
    } else if (n.kind === "field") {
      row(dl, "What it is", d.description); row(dl, "Dataset", d.dataset); row(dl, "Type", d.datatype); row(dl, "Time field", d.is_time ? "yes" : ""); row(dl, "Expression", d.expression, true);
      row(dl, "Used by metrics", relatedNames(n, function (e, x) { return e.kind === "uses_field" && e.t === x ? e.s : null; }));
    } else {
      row(dl, "Another name for", byId[d.names] ? byId[d.names].label : d.names);
    }
    row(dl, "Also called", relatedNames(n, function (e, x) { return e.kind === "synonym_of" && e.t === x ? e.s : null; }));
    side.appendChild(dl);
  }

  document.getElementById("search").addEventListener("input", function (ev) { query = ev.target.value; highlight(); });
  document.getElementById("reset").addEventListener("click", function () { selected = null; query = ""; document.getElementById("search").value = ""; highlight(); showDetails(null); alpha = 1; tick(); });
  showFields.addEventListener("change", applyVisibility); showSyn.addEventListener("change", applyVisibility);
  window.addEventListener("resize", fit);
  showSyn.checked = data.nodes.length <= 40;  // big models start uncluttered; tick "Synonyms" to add them
  applyVisibility();
})();
</script>
</body>
</html>
"""
