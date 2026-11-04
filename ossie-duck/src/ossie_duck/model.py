"""Load, validate and index an Apache Ossie semantic model (spec 0.2.0.dev0).

Validation happens in two layers:

1. JSON Schema validation against the bundled ``ossie-schema.json``.
2. Semantic checks the schema cannot express: unique names, relationship
   targets, and the metric scoping / name resolution rules from the spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from difflib import get_close_matches
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import sqlglot
import yaml
from jsonschema import Draft202012Validator
from sqlglot import exp
from sqlglot.errors import SqlglotError

SPEC_VERSION = "0.2.0.dev0"

#: Order in which dialect entries are tried when no top-level ``sql`` is given.
#: OSSIE_SQL_2026 and ANSI_SQL are passed to DuckDB as-is (no transpilation).
DIALECT_PREFERENCE = ("OSSIE_SQL_2026", "DUCKDB", "ANSI_SQL")

TEMPORAL_TYPES = frozenset({"Date", "Time", "DateTime", "DateTimeTz"})


class OssieError(Exception):
    """Base class for all errors raised by this package."""


@dataclass(frozen=True)
class Issue:
    level: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper()}: {self.where}: {self.message}"


class ModelValidationError(OssieError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("\n".join(str(i) for i in issues))


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Field:
    name: str
    expression: str | None  # SQL usable on DuckDB, or None if no usable dialect
    datatype: str | None = None
    description: str = ""
    is_time: bool = False
    has_dimension_block: bool = False
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Metric:
    name: str
    expression: str | None
    dataset: str | None = None  # None => model-scoped
    datatype: str | None = None
    description: str = ""
    synonyms: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        """How a consumer refers to the metric (spec: Metric Scoping)."""
        return f"{self.dataset}.{self.name}" if self.dataset else self.name


@dataclass(frozen=True)
class Relationship:
    name: str
    from_dataset: str  # the "many" side
    to_dataset: str  # the "one" side
    from_columns: tuple[str, ...]
    to_columns: tuple[str, ...]


@dataclass
class Dataset:
    name: str
    source: str
    primary_key: tuple[str, ...] = ()
    unique_keys: tuple[tuple[str, ...], ...] = ()
    description: str = ""
    synonyms: tuple[str, ...] = ()
    fields: dict[str, Field] = field(default_factory=dict)
    metrics: dict[str, Metric] = field(default_factory=dict)


@dataclass
class SemanticModel:
    name: str
    version: str = SPEC_VERSION
    description: str = ""
    ai_instructions: str = ""
    datasets: dict[str, Dataset] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    metrics: dict[str, Metric] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    # -- lookups ----------------------------------------------------------- #

    def all_metrics(self) -> list[Metric]:
        out = list(self.metrics.values())
        for ds in self.datasets.values():
            out.extend(ds.metrics.values())
        return out

    def all_fields(self) -> list[tuple[Dataset, Field]]:
        return [(ds, f) for ds in self.datasets.values() for f in ds.fields.values()]

    def resolve_metric(self, ref: str) -> Metric:
        """Resolve ``dataset.metric`` or a bare metric name.

        A bare name matches a model-scoped metric first, then a dataset-scoped
        metric if exactly one dataset declares it.
        """
        from .errors import QueryError  # local import: avoids a cycle at import time

        known = [m.ref for m in self.all_metrics()]
        if "." in ref:
            ds_name, _, name = ref.partition(".")
            ds = self.datasets.get(ds_name)
            if ds and name in ds.metrics:
                return ds.metrics[name]
            raise QueryError(f"unknown metric {ref!r}.{suggest(ref, known)}")
        if ref in self.metrics:
            return self.metrics[ref]
        hits = [ds.metrics[ref] for ds in self.datasets.values() if ref in ds.metrics]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            options = ", ".join(m.ref for m in hits)
            raise QueryError(f"metric name {ref!r} is ambiguous; use one of: {options}")
        raise QueryError(f"unknown metric {ref!r}.{suggest(ref, known)}")

    def resolve_field(self, ref: str) -> tuple[Dataset, Field]:
        """Resolve ``dataset.field`` or a bare field name that is unique."""
        from .errors import QueryError

        known = [f"{ds.name}.{f.name}" for ds, f in self.all_fields()]
        if "." in ref:
            ds_name, _, fname = ref.partition(".")
            ds = self.datasets.get(ds_name)
            if ds and fname in ds.fields:
                return ds, ds.fields[fname]
            raise QueryError(f"unknown field {ref!r}.{suggest(ref, known)}")
        hits = [(ds, ds.fields[ref]) for ds in self.datasets.values() if ref in ds.fields]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            options = ", ".join(f"{ds.name}.{ref}" for ds, _ in hits)
            raise QueryError(f"field name {ref!r} is ambiguous; use one of: {options}")
        raise QueryError(f"unknown field {ref!r}.{suggest(ref, known)}")


def suggest(name: str, options: list[str]) -> str:
    close = get_close_matches(name, options, n=3, cutoff=0.5)
    return f" Did you mean: {', '.join(close)}?" if close else ""


# --------------------------------------------------------------------------- #
# SQL helpers
# --------------------------------------------------------------------------- #


def parse_sql(sql: str) -> exp.Expression:
    """Parse a scalar/aggregate expression. Raises ``SqlglotError`` on failure."""
    return sqlglot.parse_one(sql, read="duckdb")


def pick_expression(expression: dict[str, Any] | None) -> str | None:
    """Choose the SQL text to run on DuckDB from an Ossie ``Expression`` object.

    The top-level ``sql`` (OSSIE_SQL_2026) is authoritative when present;
    otherwise the first matching entry of ``DIALECT_PREFERENCE``.
    """
    if not expression:
        return None
    if expression.get("sql"):
        return expression["sql"]
    by_dialect = {
        str(d.get("dialect", "")).upper(): d.get("expression")
        for d in expression.get("dialects", [])
    }
    for dialect in DIALECT_PREFERENCE:
        if by_dialect.get(dialect):
            return by_dialect[dialect]
    return None


def _dialects_of(expression: dict[str, Any] | None) -> list[str]:
    if not expression:
        return []
    return [str(d.get("dialect")) for d in expression.get("dialects", [])]


def _ai(ctx: Any) -> tuple[str, tuple[str, ...]]:
    """Return (instructions, synonyms) from an ``ai_context`` value."""
    if ctx is None:
        return "", ()
    if isinstance(ctx, str):
        return ctx, ()
    return str(ctx.get("instructions", "")), tuple(ctx.get("synonyms", ()))


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    text = resources.files("ossie_duck").joinpath("schema/ossie-schema.json").read_text("utf-8")
    return Draft202012Validator(json.loads(text))


def _fmt_path(parts) -> str:
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "document"


def validate_schema(doc: dict[str, Any]) -> list[Issue]:
    """Validate a parsed document against the Ossie JSON Schema."""
    if "semantic_model" in doc:
        return [
            Issue(
                "error",
                "document",
                "uses the pre-0.2.0 `semantic_model` array shape. This tool implements the "
                f"flat document shape of spec {SPEC_VERSION}: move the model's properties to the "
                "document root (see 'Migrating earlier document shapes' in core-spec/spec.md).",
            )
        ]
    version = doc.get("version")
    if version != SPEC_VERSION:
        return [
            Issue(
                "error",
                "version",
                f"document declares version {version!r}; this tool implements {SPEC_VERSION!r}",
            )
        ]
    errors = sorted(_validator().iter_errors(doc), key=lambda e: list(map(str, e.absolute_path)))
    return [Issue("error", _fmt_path(e.absolute_path), e.message) for e in errors]


# --------------------------------------------------------------------------- #
# Building and checking
# --------------------------------------------------------------------------- #


def _build_metric(raw: dict[str, Any], dataset: str | None) -> Metric:
    _, synonyms = _ai(raw.get("ai_context"))
    return Metric(
        name=raw["name"],
        expression=pick_expression(raw.get("expression")),
        dataset=dataset,
        datatype=raw.get("datatype"),
        description=raw.get("description", ""),
        synonyms=synonyms,
    )


def _build(doc: dict[str, Any], issues: list[Issue]) -> SemanticModel:
    instructions, _ = _ai(doc.get("ai_context"))
    model = SemanticModel(
        name=doc["name"],
        version=doc["version"],
        description=doc.get("description", ""),
        ai_instructions=instructions,
    )

    for i, raw_ds in enumerate(doc["datasets"]):
        where = f"datasets[{i}] ({raw_ds['name']})"
        if raw_ds["name"] in model.datasets:
            issues.append(Issue("error", where, "duplicate dataset name"))
            continue
        _, ds_synonyms = _ai(raw_ds.get("ai_context"))
        ds = Dataset(
            name=raw_ds["name"],
            source=raw_ds["source"],
            primary_key=tuple(raw_ds.get("primary_key", ())),
            unique_keys=tuple(tuple(k) for k in raw_ds.get("unique_keys", ())),
            description=raw_ds.get("description", ""),
            synonyms=ds_synonyms,
        )
        for j, raw_f in enumerate(raw_ds.get("fields", [])):
            if raw_f["name"] in ds.fields:
                issues.append(Issue("error", f"{where}.fields[{j}]", f"duplicate field {raw_f['name']!r}"))
                continue
            dimension = raw_f.get("dimension")
            datatype = raw_f.get("datatype")
            is_time = (dimension or {}).get("is_time")
            if is_time is None:  # spec: defaults to true for temporal datatypes
                is_time = datatype in TEMPORAL_TYPES
            _, f_syn = _ai(raw_f.get("ai_context"))
            ds.fields[raw_f["name"]] = Field(
                name=raw_f["name"],
                expression=pick_expression(raw_f.get("expression")),
                datatype=datatype,
                description=raw_f.get("description", ""),
                is_time=bool(is_time),
                has_dimension_block=dimension is not None,
                synonyms=f_syn,
            )
            if ds.fields[raw_f["name"]].expression is None:
                issues.append(
                    Issue(
                        "warning",
                        f"{where}.fields[{j}] ({raw_f['name']})",
                        "no expression this tool can run "
                        f"(declared dialects: {_dialects_of(raw_f.get('expression'))})",
                    )
                )
        for j, raw_m in enumerate(raw_ds.get("metrics", [])):
            name = raw_m["name"]
            if name in ds.fields or name in ds.metrics:
                issues.append(
                    Issue("error", f"{where}.metrics[{j}]", f"{name!r} collides with another field or metric in this dataset")
                )
                continue
            ds.metrics[name] = _build_metric(raw_m, ds.name)
        model.datasets[ds.name] = ds

    for i, raw_r in enumerate(doc.get("relationships", [])):
        model.relationships.append(
            Relationship(
                name=raw_r["name"],
                from_dataset=raw_r["from"],
                to_dataset=raw_r["to"],
                from_columns=tuple(raw_r["from_columns"]),
                to_columns=tuple(raw_r["to_columns"]),
            )
        )

    for i, raw_m in enumerate(doc.get("metrics", [])):
        if raw_m["name"] in model.metrics:
            issues.append(Issue("error", f"metrics[{i}]", f"duplicate metric {raw_m['name']!r}"))
            continue
        model.metrics[raw_m["name"]] = _build_metric(raw_m, None)
    return model


def _check_metric(model: SemanticModel, metric: Metric, issues: list[Issue]) -> None:
    where = f"metric {metric.ref}"
    if metric.expression is None:
        issues.append(Issue("warning", where, "no expression this tool can run"))
        return
    try:
        tree = parse_sql(metric.expression)
    except SqlglotError as exc:
        issues.append(Issue("error", where, f"cannot parse expression: {exc}"))
        return
    if not (tree.find(exp.AggFunc) or tree.find(exp.Window)):
        issues.append(Issue("warning", where, "expression contains no aggregate or window function"))
    for col in tree.find_all(exp.Column):
        if col.args.get("db"):
            issues.append(Issue("error", where, f"{col.sql()!r}: references must be `field` or `dataset.field`"))
            continue
        table, name = col.table or None, col.name
        if metric.dataset is not None:  # dataset-scoped: single-part names
            if table and table != metric.dataset:
                issues.append(
                    Issue("error", where, f"dataset-scoped metric references {table}.{name}; "
                          "a metric that spans datasets belongs in the model-root `metrics`")
                )
            elif name not in model.datasets[metric.dataset].fields:
                issues.append(Issue("error", where, f"{name!r} is not a declared field of dataset {metric.dataset!r}"))
            elif table:
                issues.append(Issue("warning", where, f"{col.sql()!r} should be written as the single-part name {name!r}"))
        else:  # model-scoped: dataset.field
            if not table:
                issues.append(Issue("error", where, f"{name!r} must be qualified as dataset.field"))
            elif table not in model.datasets:
                issues.append(Issue("error", where, f"unknown dataset {table!r} in {table}.{name}"))
            elif name not in model.datasets[table].fields:
                issues.append(Issue("error", where, f"{name!r} is not a declared field of dataset {table!r}"))


def _check(model: SemanticModel) -> list[Issue]:
    issues: list[Issue] = []
    for ds in model.datasets.values():
        where = f"dataset {ds.name}"
        for key in (ds.primary_key, *ds.unique_keys):
            for col in key:
                if col not in ds.fields:
                    issues.append(Issue("error", where, f"key column {col!r} is not a declared field"))
        for f in ds.fields.values():
            if f.expression is not None:
                try:
                    parse_sql(f.expression)
                except SqlglotError as exc:
                    issues.append(Issue("error", f"{where}.{f.name}", f"cannot parse expression: {exc}"))
        for m in ds.metrics.values():
            _check_metric(model, m, issues)

    for r in model.relationships:
        where = f"relationship {r.name}"
        for side, ds_name, cols in (("from", r.from_dataset, r.from_columns), ("to", r.to_dataset, r.to_columns)):
            ds = model.datasets.get(ds_name)
            if ds is None:
                issues.append(Issue("error", where, f"`{side}` dataset {ds_name!r} does not exist"))
                continue
            for c in cols:
                if c not in ds.fields:
                    issues.append(Issue("error", where, f"{c!r} is not a declared field of {ds_name!r}"))
        if len(r.from_columns) != len(r.to_columns):
            issues.append(Issue("error", where, "from_columns and to_columns must have the same length"))

    for m in model.metrics.values():
        _check_metric(model, m, issues)
    return issues


# --------------------------------------------------------------------------- #
# Public loaders
# --------------------------------------------------------------------------- #


def parse_model(document: str | dict[str, Any], *, strict: bool = True) -> SemanticModel:
    """Parse and validate a model from YAML/JSON text or an already-parsed dict.

    With ``strict=True`` (default) any error-level issue raises
    :class:`ModelValidationError`; warnings are kept on ``model.issues``.
    """
    if isinstance(document, str):
        try:
            document = yaml.safe_load(document)
        except yaml.YAMLError as exc:
            raise ModelValidationError([Issue("error", "document", f"not valid YAML/JSON: {exc}")]) from exc
    if not isinstance(document, dict):
        raise ModelValidationError([Issue("error", "document", "expected a mapping at the document root")])

    schema_issues = validate_schema(document)
    if schema_issues:
        raise ModelValidationError(schema_issues)

    issues: list[Issue] = []
    model = _build(document, issues)
    issues.extend(_check(model))
    model.issues = issues
    errors = [i for i in issues if i.level == "error"]
    if strict and errors:
        raise ModelValidationError(errors)
    return model


def load_model(path: str | Path, *, strict: bool = True) -> SemanticModel:
    """Load a model from a ``.yaml`` / ``.yml`` / ``.json`` file."""
    return parse_model(Path(path).read_text(encoding="utf-8"), strict=strict)
