"""Project configuration. Reads .env if present, falls back to sane defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    project_root: Path
    duckdb_path: Path
    schema_registry_path: Path
    stock_universe: str
    backfill_years: int

    @classmethod
    def load(cls) -> Config:
        root = _project_root()
        return cls(
            project_root=root,
            duckdb_path=root / os.getenv("DUCKDB_PATH", "data/markets.duckdb"),
            schema_registry_path=root / os.getenv("SCHEMA_REGISTRY_PATH", "data/schema_registry.json"),
            stock_universe=os.getenv("STOCK_UNIVERSE", "NIFTY_500"),
            backfill_years=int(os.getenv("BACKFILL_YEARS", "20")),
        )


CONFIG = Config.load()
