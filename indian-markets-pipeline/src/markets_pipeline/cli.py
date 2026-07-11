"""Command-line entrypoint. Wraps extract -> load for ad-hoc runs.

Usage:
  python -m markets_pipeline.cli smoke           # 5 stocks + 5 MFs, last 90 days
  python -m markets_pipeline.cli backfill        # full universe, BACKFILL_YEARS history
  python -m markets_pipeline.cli daily           # incremental: yesterday only
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

import polars as pl

from .config import CONFIG
from .duckdb_client import connect
from .extractors import mutual_funds, stocks, universe
from .loaders import DuckDBLoader
from .schema import SchemaEvolution, SchemaRegistry

log = logging.getLogger(__name__)


# Five well-known SIP-friendly schemes for the smoke test.
# (mfapi.in resolves these AMFI codes — verified at time of writing.)
_SMOKE_MF_CODES = [
    120503,  # Parag Parikh Flexi Cap (Direct, Growth)
    119598,  # UTI Nifty 50 Index Fund (Direct, Growth)
    118989,  # HDFC Index Fund - Sensex (Direct, Growth)
    122639,  # Mirae Asset Large Cap (Direct, Growth)
    120716,  # Axis Long Term Equity ELSS (Direct, Growth)
]


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )


def _run_load(
    loader: DuckDBLoader, table: str, df: pl.DataFrame, pk: list[str]
) -> None:
    result = loader.load(table, df, pk)
    log.info(
        "TABLE=%s in=%s loaded=%s rejected=%s changes=%s",
        result.table,
        result.rows_in,
        result.rows_loaded,
        result.rows_rejected,
        [c.kind.value for c in result.schema_changes],
    )


def _load_stocks(loader: DuckDBLoader, tickers: list[str], start: date, end: date) -> None:
    log.info("Fetching prices for %s tickers", len(tickers))
    df = stocks.fetch_prices(tickers, start=start, end=end)
    _run_load(loader, "stock_prices", df, ["ticker", "date"])


def _load_mutual_funds(loader: DuckDBLoader, codes: list[int], since: date | None) -> None:
    log.info("Fetching NAVs for %s schemes", len(codes))
    df = mutual_funds.fetch_navs(codes, since=since)
    _run_load(loader, "mf_navs", df, ["scheme_code", "date"])


def _scheme_master(loader: DuckDBLoader) -> None:
    log.info("Fetching MF scheme master")
    df = universe.fetch_mf_scheme_master()
    _run_load(loader, "mf_scheme_master", df, ["scheme_code"])


def cmd_smoke(args: argparse.Namespace) -> None:
    end = date.today()
    start = end - timedelta(days=90)
    tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

    with connect(CONFIG.duckdb_path) as conn:
        registry = SchemaRegistry(CONFIG.schema_registry_path)
        evo = SchemaEvolution(conn, registry)
        loader = DuckDBLoader(conn, evo)

        _load_stocks(loader, tickers, start, end)
        _load_mutual_funds(loader, _SMOKE_MF_CODES, since=start)

        # Sanity: row counts
        for tbl in ("stock_prices", "mf_navs"):
            try:
                n = conn.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
                log.info("%s row count = %s", tbl, n)
            except Exception as e:
                log.warning("%s missing: %s", tbl, e)


def cmd_backfill(args: argparse.Namespace) -> None:
    end = date.today()
    start = end - timedelta(days=365 * CONFIG.backfill_years)
    tickers = universe.get_stock_universe(CONFIG.stock_universe)

    with connect(CONFIG.duckdb_path) as conn:
        registry = SchemaRegistry(CONFIG.schema_registry_path)
        evo = SchemaEvolution(conn, registry)
        loader = DuckDBLoader(conn, evo)

        _scheme_master(loader)
        _load_stocks(loader, tickers, start, end)

        # MF backfill: pull every scheme would be ~50 GB of HTTP. For backfill
        # we keep the same SIP-friendly subset; phase 4 introduces a curated
        # universe based on category + AUM filters.
        _load_mutual_funds(loader, _SMOKE_MF_CODES, since=start)


def cmd_daily(args: argparse.Namespace) -> None:
    yesterday = date.today() - timedelta(days=1)
    tickers = universe.get_stock_universe(CONFIG.stock_universe)

    with connect(CONFIG.duckdb_path) as conn:
        registry = SchemaRegistry(CONFIG.schema_registry_path)
        evo = SchemaEvolution(conn, registry)
        loader = DuckDBLoader(conn, evo)

        _load_stocks(loader, tickers, yesterday, yesterday)
        _load_mutual_funds(loader, _SMOKE_MF_CODES, since=yesterday)


def cmd_features(args: argparse.Namespace) -> None:
    from .transformers import _pipeline

    counts = _pipeline.build_all()
    log.info("FEATURES BUILT: %s", counts)


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser("markets-pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("smoke", help="5 stocks + 5 MFs, last 90 days").set_defaults(func=cmd_smoke)
    sub.add_parser("backfill", help="Full universe, BACKFILL_YEARS history").set_defaults(
        func=cmd_backfill
    )
    sub.add_parser("daily", help="Yesterday only — incremental").set_defaults(func=cmd_daily)
    sub.add_parser("features", help="Compute features + recommendations").set_defaults(
        func=cmd_features
    )
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
