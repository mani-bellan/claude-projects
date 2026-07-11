"""Glue: compute features + recommendations and write to DuckDB."""

from __future__ import annotations

import logging

from ..duckdb_client import connect
from ..config import CONFIG
from ..loaders import DuckDBLoader
from ..schema import SchemaEvolution, SchemaRegistry
from . import features, recommendations

log = logging.getLogger(__name__)


def build_all() -> dict:
    """Compute both stock and MF features and recommendations. Returns row counts."""
    out: dict = {}
    with connect(CONFIG.duckdb_path) as conn:
        registry = SchemaRegistry(CONFIG.schema_registry_path)
        loader = DuckDBLoader(conn, SchemaEvolution(conn, registry))

        # Stocks
        sf = features.compute_stock_features(conn)
        if not sf.is_empty():
            r1 = loader.load("stock_features", sf, primary_key=["ticker"])
            sr = recommendations.stock_recommendations(sf)
            r2 = loader.load("stock_recommendations", sr, primary_key=["ticker"])
            out["stock_features"] = r1.rows_loaded
            out["stock_recommendations"] = r2.rows_loaded
        else:
            log.warning("No stock_prices rows; skipping stock features")

        # Mutual funds
        mf = features.compute_mf_features(conn)
        if not mf.is_empty():
            r1 = loader.load("mf_features", mf, primary_key=["scheme_code"])
            mr = recommendations.mf_recommendations(mf)
            r2 = loader.load("mf_recommendations", mr, primary_key=["scheme_code"])
            out["mf_features"] = r1.rows_loaded
            out["mf_recommendations"] = r2.rows_loaded
        else:
            log.warning("No mf_navs rows; skipping MF features")

    return out
